#!/usr/bin/env python3
"""Bee's common judge: static analysis of the judged project's compiled objects.

The judge checks from outside that the project's OUTPUTS are correct. What it cannot see from
outside is code that attacks the measurement itself: direct system calls, launching
other programs, Valgrind client requests (which suspend the instruction count), reading
the clock, constructors run before the harness, symbols that replace the harness's or the libc's
(memcmp, clock_gettime…). These constructs have no business in a computing library (compression,
parsing, encoding); they show in the compiled objects. This module compares the surveys of the PR (B)
with those of the base (A), produced in the container by the plugin's build script (nm, objdump),
and lists what B adds. The plugin gives the project's namespace (PREFIXES) and the external
functions it may call besides the common list (PERMIS).

A suspicious construct is not a fault: it only withdraws the trust in the measurements, and
the registry then requires a guardian's review (R3). This module reads only text and bytes; it executes nothing.
"""

import re
import struct
from collections import Counter

# Functions that serve to deceive the measurement (clock, processes, environment, signals, system calls), not to
# compress or to parse: never allowed, and flagged by their exact name BEFORE any exemption by the project's
# namespace or by the plugin's PERMIS list (adversarial review no. 2 of 28 October: a prefix « ge » covered getenv).
NEVER_ALLOWED = frozenset({
    "syscall", "clock_gettime", "clock_getres", "gettimeofday", "time", "times", "getrusage", "fork", "vfork",
    "clone", "execve", "execv", "execvp", "execl", "execlp", "system", "popen", "posix_spawn", "dlopen", "dlsym",
    "getenv", "secure_getenv", "ptrace", "prctl", "signal", "sigaction", "raise", "kill", "alarm", "setitimer",
    "sched_setaffinity", "mprotect",
})

# Functions of the libc a computing library may call without changing anything in the measurement: memory and strings.
UNDEFINED_ALLOWED = frozenset({
    "memcpy", "memmove", "memset", "memcmp", "malloc", "calloc", "realloc", "free", "strlen",
    "abort", "__assert_fail", "__stack_chk_fail", "__memcpy_chk", "__memmove_chk", "__memset_chk",
    "_GLOBAL_OFFSET_TABLE_",
})

# Instructions with no use in a computing library, but useful to deceive a measurement or to escape it.
SUSPICIOUS_MNEMONICS = {
    "syscall": "direct system call",
    "sysenter": "direct system call",
    "int": "software interrupt (32-bit system call or breakpoint)",
    "int3": "breakpoint",
    "rdtsc": "reading the cycle counter",
    "rdtscp": "reading the cycle counter",
    "rdpmc": "reading a performance counter",
    "rdpid": "reading the processor id",
    "rdrand": "hardware random number",
    "rdseed": "hardware random number",
    "cpuid": "processor identification (detecting an emulator or Valgrind)",
    "xgetbv": "reading the processor's state",
    "(bad)": "bytes the disassembler cannot decode",
    ".byte": "bytes the disassembler cannot decode",
    "preambule_valgrind": "Valgrind client request preamble (suspends the instruction count)",
    "segment_wx": "memory both writable and executable in the linked program",
    "pile_executable": "executable stack in the linked program",
}
# Preamble of Valgrind's client requests on x86-64: rol $3, $13, $61, $51 on %rdi.
VALGRIND_PREAMBLE = re.compile(r"\brol\s+\$0x(?:3|d|3d|33),%rdi\b")
SEQUENCES = {nom: re.compile(b"(?=(" + reason + b"))") for nom, reason in (
    ("syscall", rb"\x0f\x05"), ("sysenter", rb"\x0f\x34"), ("int", rb"\xcd\x80"), ("rdtsc", rb"\x0f\x31"),
    ("rdtscp", rb"\x0f\x01\xf9"), ("rdpmc", rb"\x0f\x33"), ("cpuid", rb"\x0f\xa2"), ("xgetbv", rb"\x0f\x01\xd0"),
    ("rdrand", rb"\x0f\xc7[\xf0-\xf7]"), ("rdseed", rb"\x0f\xc7[\xf8-\xff]"), ("rdpid", rb"\xf3[\x40-\x4f]?\x0f\xc7[\xf8-\xff]"),
    ("preambule_valgrind", rb"\x48\xc1\xc7\x03\x48\xc1\xc7\x0d\x48\xc1\xc7\x3d\x48\xc1\xc7\x33"))}

DETAIL_MAX = 300  # characters of a detail: names, paths and extracts come from the judged code (ruche-0117)
ALLOWED_SECTIONS = re.compile(
    r"^\.(?:text(?:\.(?:unlikely|hot|cold)(?:\..*)?)?|text\.[A-Za-z0-9_]+|rodata(?:\..*)?|data(?:\..*)?|bss(?:\..*)?"
    r"|debug_.*|note(?:\..*)?|comment|eh_frame|group|rela?\..*)$")
FORBIDDEN_SECTIONS = re.compile(r"^\.(?:init_array|fini_array|preinit_array|ctors|dtors|init|fini|text\.startup|text\.exit)(?:\..*)?$")

# Judged files, read whole (each file of B against the same file of A): words with no business in the project.
SOURCE_WORDS = [
    (re.compile(r"\b(?:__asm__|__asm|asm)\b"), "inline assembly"),
    (re.compile(r"__attribute(?:__)?\s*\(\s*\((?:[^()]|\([^()]*\))*?(?:constructor|destructor|ifunc|section|weak|alias)"),
     "link or initialization attribute"),
    (re.compile(r"(?:#|%:)\s*(?:include(?:_next)?|import)\s*(?:[<\"](?:sys/|unistd\.h|dlfcn\.h|signal\.h|time\.h|sched\.h|pthread\.h"
                r"|fcntl\.h|cpuid\.h|valgrind/)|[^\s<\"])"),
     "system header (processes, clock, signals, Valgrind)"),
    (re.compile(r"\b(?:getenv|RUNNING_ON_VALGRIND|VALGRIND_\w+|CACHEGRIND_\w+|CALLGRIND_\w+|dlsym|dlopen)\b"),
     "detection of the measurement environment"),
    (re.compile(r"\b(?:__builtin_ia32_(?:rdtscp?|rdpmc|rdrand\w*|rdseed\w*|rdpid|xgetbv)|__?rdtscp?|__rdpmc|_xgetbv|_rd(?:rand|seed)\w*"
                r"|__cpuid\w*|__get_cpuid\w*|__builtin_cpu_(?:supports|init|is))\b"),
     "reading the processor or the clock"),
    # This scan of the text is only a net: token pasting (« a##sm ») or _Pragma can
    # form a forbidden word the patterns above do not see (adversarial review of 28 October). The analysis
    # of the objects sees the code produced.
    (re.compile(r"##|%:%:|\b_Pragma\b|(?:#|%:)\s*pragma\b"), "token pasting or pragma (can form a forbidden word)"),
]


def symbols(text):
    """nm -P -A: « file.o: name type value [size] ». Returns {name: (type, file)}."""
    result = {}
    for line_text in text.splitlines():
        if ": " not in line_text:
            continue
        file, rest_of = line_text.split(": ", 1)
        chunks = rest_of.split()
        if len(chunks) < 2:
            continue
        nom, type_ = chunks[0], chunks[1]
        file = file.rsplit("/", 1)[-1]
        result.setdefault((nom, type_), file)
    return result


def sections(text):
    """objdump -h: section names per file."""
    names = set()
    for line_text in text.splitlines():
        chunks = line_text.split()
        if len(chunks) >= 2 and chunks[0].isdigit() and chunks[1].startswith("."):
            names.add(chunks[1])
    return names


def mnemonics_found(text):
    """objdump -d --no-show-raw-insn : suspicious mnemonics among the words of each instruction, « (bad) », Valgrind preamble."""
    accounts = {}
    for line_text in text.splitlines():
        if "\t" not in line_text:
            continue
        instruction = line_text.split("\t", 1)[1].strip()
        if not instruction:
            continue
        for word in re.sub(r"<[^>]*>|#.*", " ", instruction).replace(",", " ").split():
            if word in SUSPICIOUS_MNEMONICS:
                accounts[word] = accounts.get(word, 0) + 1
        if VALGRIND_PREAMBLE.search(instruction):
            accounts["preambule_valgrind"] = accounts.get("preambule_valgrind", 0) + 1
    return accounts


def executable_bytes(data):
    """Executable bytes of an x86-64 ELF file read from its headers: an object's sections marked executable or named
    .text*, a program's executable segments and memory flags. ValueError if any of it cannot be read."""
    if data[:7] != b"\x7fELF\x02\x01\x01" or struct.unpack_from("<H", data, 18)[0] != 62:
        raise ValueError("not an x86-64 ELF file")
    file_kind, = struct.unpack_from("<H", data, 16)
    ph, sh = struct.unpack_from("<QQ", data, 32)
    ph_size, ph_count, sh_size, sh_count, sh_names = struct.unpack_from("<HHHHH", data, 54)

    def slice_of(beginning, size):
        if beginning + size > len(data):
            raise ValueError("header or contents beyond the end of the file")
        return data[beginning:beginning + size]
    chunks, flag_bits = [], []
    if file_kind == 1:  # relocatable object: its sections
        if sh_count == 0 or sh_names >= sh_count or sh_size < 64:
            raise ValueError("unreadable section table")
        names = struct.unpack_from("<IIQQQQ", slice_of(sh + sh_names * sh_size, 64))[4]
        for i in range(sh_count):
            nom, kind_of, attributes, _, beginning, size = struct.unpack_from("<IIQQQQ", slice_of(sh + i * sh_size, 64))
            if kind_of != 8 and (attributes & 4 or data[names + nom:names + nom + 5] == b".text"):
                if attributes & 0x800:
                    raise ValueError("compressed executable section")
                chunks.append(slice_of(beginning, size))
    else:  # linked program: what is mapped at run time
        if ph_count == 0 or ph_size < 56:
            raise ValueError("unreadable program header table")
        stack_of = None
        for i in range(ph_count):
            kind_of, attributes, beginning, _, _, size = struct.unpack_from("<IIQQQQ", slice_of(ph + i * ph_size, 56))
            if kind_of == 1 and attributes & 1:
                chunks.append(slice_of(beginning, size))
                flag_bits += ["segment_wx"] if attributes & 2 else []
            stack_of = attributes if kind_of == 0x6474E551 else stack_of
        if stack_of is None or stack_of & 1:
            flag_bits.append("pile_executable")
    return chunks, flag_bits


def occurrences(files):
    """Hits of SEQUENCES and memory flags in [(name, ELF bytes)], keyed by (file, name, bytes around); unreadable files."""
    accounts, unreadables = Counter(), []
    for nom, data in files:
        try:
            chunks, flag_bits = executable_bytes(data)
        except (ValueError, struct.error) as e:
            unreadables.append(f"{nom}: executable bytes unreadable ({e}): analysis incomplete")
            continue
        accounts.update((nom, d, b"") for d in flag_bits)
        for word, reason in SEQUENCES.items():
            accounts.update((nom, word, m[max(0, t.start() - 6):t.end(1) + 6]) for m in chunks for t in reason.finditer(m))
    return accounts, unreadables


def analyse(surveys_a, surveys_b, texts_a, texts_b, prefixes=(), allowed_set=()):
    """surveys_*: {"symboles": nm text, "sections": objdump -h text, "desassemblage": objdump -d text}.
    Also "objets" and "programme": [(name, ELF bytes)]; texts_*: the judged files of A and B, {path: text}.

    prefixes:    the project's namespace (names it defines and calls between its files);
    allowed_set: external functions allowed besides UNDEFINED_ALLOWED.
    Returns the list of suspicious constructs B adds compared with A (a list of dicts), each detail cut to DETAIL_MAX."""
    prefixes = tuple(prefixes)
    all_allowed = UNDEFINED_ALLOWED | frozenset(allowed_set)
    suspects = []
    sym_a, sym_b = symbols(surveys_a["symboles"]), symbols(surveys_b["symboles"])
    defined_a = {nom for (nom, t) in sym_a if t not in "Uuvw" and t.isupper()}
    undefined_a = {nom for (nom, t) in sym_a if t in ("U", "w", "v")}
    for (nom, t), file in sorted(sym_b.items()):
        if nom in NEVER_ALLOWED and (nom, t) not in sym_a:
            suspects.append({"type": "appel_interdit" if t in ("U", "w", "v") else "symbole_interdit",
                             "detail": f"{nom} ({file}): a function that serves to deceive the measurement (never allowed)"})
        elif t in ("i", "u") and (nom, t) not in sym_a:
            suspects.append({"type": "symbole", "detail": f"{nom} ({file}): indirect function or unique symbol (type {t})"})
        elif t in ("U", "w", "v"):
            if nom not in all_allowed and nom not in undefined_a and not (prefixes and nom.startswith(prefixes)):
                suspects.append({"type": "appel_externe", "detail": f"{nom} ({file}): external function outside the allowed list"})
        elif t.isupper() and nom not in defined_a and not (prefixes and nom.startswith(prefixes)):
            suspects.append({"type": "symbole_defini", "detail": f"{nom} ({file}): global symbol outside the project's namespace "
                                                                 "(it could replace a function of the harness or of the libc)"})
    sec_a, sec_b = sections(surveys_a["sections"]), sections(surveys_b["sections"])
    for nom in sorted(sec_b - sec_a):
        if FORBIDDEN_SECTIONS.match(nom) or not ALLOWED_SECTIONS.match(nom):
            suspects.append({"type": "section", "detail": f"{nom}: section run before the program, or unusual"})
    mn_a, mn_b = mnemonics_found(surveys_a["desassemblage"]), mnemonics_found(surveys_b["desassemblage"])
    for word, n in sorted(mn_b.items()):
        if n > mn_a.get(word, 0):
            cause = "Valgrind client request preamble (suspends the instruction count)" if word == "preambule_valgrind" \
                else SUSPICIOUS_MNEMONICS[word]
            suspects.append({"type": "instruction", "detail": f"{word}: {n} occurrence(s) against {mn_a.get(word, 0)} in the base ({cause})"})
    for survey, or_else in (("objets", "the objects' executable sections"), ("programme", "the linked program's executable segments")):
        (oc_a, unreadable_a), (oc_b, unreadable_b) = occurrences(surveys_a[survey]), occurrences(surveys_b[survey])
        suspects += [{"type": "analyse_incomplete", "detail": d} for d in unreadable_a + unreadable_b]
        for (nom, word, around), n in sorted(oc_b.items()):
            if n > oc_a[(nom, word, around)]:
                suspects.append({"type": "octets", "detail": f"{word}: {n} occurrence(s) at {around.hex()} in {nom} ({or_else}), "
                                                             f"against {oc_a[(nom, word, around)]} in the base ({SUSPICIOUS_MNEMONICS[word]})"})
    seen_a = text_constructs(texts_a)
    for (path, cause, extract), n in sorted(text_constructs(texts_b).items()):
        if n > seen_a[(path, cause, extract)]:
            suspects.append({"type": "source", "detail": f"{cause}: « {extract[:160]} » ({path})"})
    return [dict(s, detail=s["detail"] if len(s["detail"]) <= DETAIL_MAX else s["detail"][:DETAIL_MAX - 1] + "…") for s in suspects]


def text_constructs(texts_of):
    """{(file, reason, extract): n} for MOTS_SOURCE over whole files {path: text}, line splices joined as the preprocessor
    does, across line breaks; the extract is the text of the lines a match spans, whitespace collapsed."""
    accounts = Counter()
    for path, text in texts_of.items():
        text = re.sub(r"\\[ \t\f\v\0]*(?:\r\n?|\n)", "", text)
        for reason, cause in SOURCE_WORDS:
            for m in reason.finditer(text):
                beginning, end = text.rfind("\n", 0, m.start()) + 1, text.find("\n", m.end())
                accounts[(path, cause, " ".join(text[beginning:end if end >= 0 else None].split()))] += 1
    return accounts
