#!/usr/bin/env python3
"""Introspect the REAL installed genblaze surface to resolve SDKCHK #1-#9.

This is the reproduction artifact for the SDKCHK ledger: run it and
every claim about the SDK shape is re-derivable. It never guesses — it reads the
installed modules. Guarded so one missing symbol never aborts the whole dump.

    uv run python scripts/sdk_introspect.py
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

SEP = "=" * 72


def _sig(obj) -> str:
    try:
        return str(inspect.signature(obj))
    except (ValueError, TypeError):
        return "(<no signature>)"


def _first_doc(obj) -> str:
    doc = inspect.getdoc(obj) or ""
    return doc.strip().splitlines()[0] if doc.strip() else ""


def dump_module_symbols(modname: str) -> None:
    print(SEP)
    print(f"MODULE  {modname}")
    print(SEP)
    try:
        mod = importlib.import_module(modname)
    except Exception as e:  # noqa: BLE001
        print(f"  !! import failed: {type(e).__name__}: {e}")
        return
    exported = getattr(mod, "__all__", None)
    names = sorted(exported) if exported else sorted(
        n for n in dir(mod) if not n.startswith("_")
    )
    print(f"  __all__ defined: {exported is not None}  ({len(names)} public names)")
    for n in names:
        obj = getattr(mod, n, None)
        kind = type(obj).__name__
        origin = getattr(obj, "__module__", "?")
        if inspect.isclass(obj) or inspect.isfunction(obj):
            print(f"  - {n:32} {kind:12} {origin}")
        else:
            print(f"  - {n:32} {kind:12} = {obj!r}"[:110])


def walk_package(pkgname: str) -> list[str]:
    """Return all importable submodule names under a package."""
    found = [pkgname]
    try:
        pkg = importlib.import_module(pkgname)
    except Exception as e:  # noqa: BLE001
        print(f"  !! cannot import {pkgname}: {e}")
        return found
    if not hasattr(pkg, "__path__"):
        return found
    for info in pkgutil.walk_packages(pkg.__path__, prefix=pkgname + "."):
        found.append(info.name)
    return found


def probe(title: str, fn) -> None:
    print()
    print("#" * 72)
    print(f"# {title}")
    print("#" * 72)
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        print(f"  !! probe error: {type(e).__name__}: {e}")


def cls_detail(modname: str, clsname: str, methods: list[str]) -> None:
    mod = importlib.import_module(modname)
    cls = getattr(mod, clsname, None)
    if cls is None:
        print(f"  {clsname}: NOT FOUND in {modname}")
        return
    print(f"  {clsname}  (from {cls.__module__})")
    print(f"    __init__{_sig(cls.__init__)}")
    if inspect.isabstract(cls):
        print(f"    ABSTRACT methods: {sorted(getattr(cls, '__abstractmethods__', set()))}")
    mro = [c.__name__ for c in cls.__mro__]
    print(f"    MRO: {mro}")
    for m in methods:
        meth = getattr(cls, m, None)
        if meth is None:
            print(f"    .{m}: MISSING")
        else:
            print(f"    .{m}{_sig(meth)}   # {_first_doc(meth)[:60]}")


def grep_source(pkgname: str, needles: list[str]) -> None:
    """Grep the installed package source for needle strings (case-insensitive)."""
    import os

    pkg = importlib.import_module(pkgname)
    root = os.path.dirname(inspect.getfile(pkg))
    hits: dict[str, list[str]] = {n: [] for n in needles}
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(dirpath, f)
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        low = line.lower()
                        for n in needles:
                            if n.lower() in low:
                                rel = os.path.relpath(path, os.path.dirname(root))
                                hits[n].append(f"{rel}:{i}: {line.strip()[:100]}")
            except OSError:
                pass
    for n in needles:
        print(f"  needle {n!r}: {len(hits[n])} hit(s)")
        for h in hits[n][:6]:
            print(f"      {h}")


def main() -> None:
    print("SDKCHK introspection — installed genblaze surface\n")

    import genblaze  # noqa: F401
    import genblaze_core

    print(f"genblaze version:       {getattr(genblaze, '__version__', '?')}")
    print(f"genblaze_core version:  {getattr(genblaze_core, '__version__', '?')}")

    # Discover the full module tree first
    probe("SDKCHK #1 — package tree (genblaze / genblaze_core / genblaze_s3)", lambda: [
        print("  " + m) for pkg in ("genblaze", "genblaze_core", "genblaze_s3")
        for m in walk_package(pkg)
    ] and None)

    probe("Top-level exports", lambda: [
        dump_module_symbols(m)
        for m in ("genblaze", "genblaze_core")
    ] and None)

    # #8 StorageBackend interface (CRITICAL for LocalDirBackend OFFLINE)
    def _sb():
        for mod in ("genblaze_core", "genblaze_core.storage", "genblaze_core.sinks",
                    "genblaze_s3", "genblaze_core.backends"):
            try:
                m = importlib.import_module(mod)
            except Exception:  # noqa: BLE001
                continue
            for cand in ("StorageBackend", "S3StorageBackend"):
                if hasattr(m, cand):
                    cls_detail(mod, cand, ["put", "get", "exists", "url", "put_object",
                                           "get_object", "write", "read", "upload",
                                           "download", "presign", "presigned_url",
                                           "list", "delete", "for_backblaze"])
    probe("SDKCHK #8 — StorageBackend abstract interface", _sb)

    # #2 read_manifest(verify=...) + strict_manifest_reads
    def _rm():
        cls_detail("genblaze_core", "ObjectStorageSink",
                   ["__init__", "read_manifest", "write", "put", "store"])
        print("\n  -- grep for strict_manifest_reads / read_manifest across genblaze_core --")
        grep_source("genblaze_core", ["strict_manifest_reads", "read_manifest",
                                      "verify=True"])
    probe("SDKCHK #2 — read_manifest(verify=True) + strict flag", _rm)

    # #3 job resumption
    probe("SDKCHK #3 — transient-error job resumption surface", lambda:
          grep_source("genblaze_core", ["resum", "resume", "transient", "checkpoint",
                                        "idempoten"]))

    # #4 CostLedger / total_cost_usd
    def _cost():
        for mod in ("genblaze_core", "genblaze_core.cost", "genblaze_core.economics"):
            try:
                m = importlib.import_module(mod)
            except Exception:  # noqa: BLE001
                continue
            if hasattr(m, "CostLedger"):
                cls_detail(mod, "CostLedger", ["add", "total", "record", "charge"])
        print("\n  -- grep total_cost_usd / cost_usd / CostLedger --")
        grep_source("genblaze_core", ["total_cost_usd", "cost_usd", "CostLedger"])
    probe("SDKCHK #4 — CostLedger / total_cost_usd per-step", _cost)

    # #5 sink-level object lock param
    probe("SDKCHK #5 — sink-level Object Lock kwarg", lambda:
          grep_source("genblaze_core", ["object_lock", "objectlock", "retention",
                                        "lock"]) )

    # #6 WebhookSink schema
    def _wh():
        for mod in ("genblaze_core", "genblaze_core.sinks"):
            try:
                m = importlib.import_module(mod)
            except Exception:  # noqa: BLE001
                continue
            for cand in ("WebhookSink", "ParquetSink"):
                if hasattr(m, cand):
                    cls_detail(mod, cand, ["__init__", "emit", "send", "handle", "write"])
    probe("SDKCHK #6 — WebhookSink / ParquetSink shape", _wh)

    # #9 conformance kit
    probe("SDKCHK #9 — provider conformance test kit", lambda:
          grep_source("genblaze_core", ["conformance", "conform", "provider_contract",
                                        "assert_provider", "test_kit"]))

    # Providers for OFFLINE (Mock/Failing/ModelError) + RetryPolicy
    def _prov():
        for mod in ("genblaze_core", "genblaze_core.providers", "genblaze_core.testing",
                    "genblaze_core.providers.testing"):
            try:
                m = importlib.import_module(mod)
            except Exception:  # noqa: BLE001
                continue
            for cand in ("MockProvider", "FailingProvider", "ModelErrorProvider",
                         "RetryPolicy", "BaseProvider", "Provider"):
                if hasattr(m, cand):
                    obj = getattr(m, cand)
                    if inspect.isclass(obj):
                        print(f"  {mod}.{cand}: __init__{_sig(obj.__init__)}")
                        if cand in ("MockProvider", "FailingProvider", "ModelErrorProvider",
                                    "BaseProvider", "Provider"):
                            pub = [n for n in dir(obj) if not n.startswith("_")]
                            print(f"      public: {pub}")
    probe("Providers — Mock/Failing/ModelError + RetryPolicy + BaseProvider", _prov)

    # Manifest / EmbedPolicy / Modality
    def _man():
        m = importlib.import_module("genblaze_core")
        for cand in ("Manifest", "EmbedPolicy", "Modality", "KeyStrategy", "URLPolicy",
                     "Pipeline", "AgentLoop", "AgentContext", "CallableEvaluator",
                     "ThresholdEvaluator", "EvaluationResult", "StepCache"):
            obj = getattr(m, cand, None)
            if obj is None:
                print(f"  {cand}: NOT top-level in genblaze_core")
                continue
            if inspect.isclass(obj):
                print(f"  {cand}: class __init__{_sig(obj.__init__)}")
                if hasattr(obj, "__members__"):  # enum
                    print(f"      members: {list(obj.__members__)}")
            else:
                print(f"  {cand}: {type(obj).__name__} = {obj!r}"[:100])
    probe("Manifest / EmbedPolicy / Modality / Pipeline / AgentLoop", _man)

    # Pipeline method shapes
    def _pipe():
        cls_detail("genblaze_core", "Pipeline",
                   ["__init__", "step", "run", "arun", "batch_run", "stream", "cache"])
    probe("Pipeline method signatures", _pipe)

    print("\n" + SEP)
    print("introspection complete")
    print(SEP)


if __name__ == "__main__":
    main()
