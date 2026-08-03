"""SDKCHK #1-#9 regression guards.

These encode what P0 verified about the REAL installed genblaze 0.4.1 surface.
If an upstream bump changes a shape we depend on, the matching test fails and
the SDKCHK ledger gets re-verified rather than silently drifting.
"""

from __future__ import annotations

import dataclasses
import inspect

import genblaze_core


def _field_names(cls) -> set[str]:
    """Field names whether cls is pydantic, a dataclass, or plain-annotated."""
    mf = getattr(cls, "model_fields", None)
    if mf:
        return set(mf)
    if dataclasses.is_dataclass(cls):
        return {f.name for f in dataclasses.fields(cls)}
    return set(getattr(cls, "__annotations__", {}))


# --- #1 umbrella pin ---------------------------------------------------------
def test_sdkchk01_umbrella_pin_and_core_floor():
    import importlib.metadata as md

    assert md.version("genblaze") == "0.4.1"
    core = md.version("genblaze-core")
    assert core >= "0.3.4"
    assert core.startswith("0.3.")  # <0.4 floor per umbrella requires_dist
    assert md.version("genblaze-s3").startswith("0.3.")


# --- #2 read_manifest(verify=True) + strict flag -----------------------------
def test_sdkchk02_read_manifest_and_strict_flag():
    from genblaze_core.storage.sink import ObjectStorageSink

    rm = inspect.signature(ObjectStorageSink.read_manifest)
    assert "verify" in rm.parameters
    assert rm.parameters["verify"].default is True

    ctor = inspect.signature(ObjectStorageSink.__init__)
    assert "strict_manifest_reads" in ctor.parameters
    assert "allow_unverified_manifest_reads" in ctor.parameters
    # strict flag also honours an env var
    import genblaze_core.storage.sink as sinkmod

    src = inspect.getsource(sinkmod)
    assert "GENBLAZE_STRICT_MANIFEST_READS" in src


# --- #3 job resumption -------------------------------------------------------
def test_sdkchk03_resumption_surface():
    from genblaze_core.pipeline.pipeline import Pipeline

    assert hasattr(Pipeline, "resume_step")
    assert hasattr(Pipeline, "aresume_step")
    from genblaze_core.providers.base import BaseProvider

    assert hasattr(BaseProvider, "resume") and hasattr(BaseProvider, "aresume")


# --- #4 cost surface: step.cost_usd, NOT a CostLedger ------------------------
def test_sdkchk04_cost_surface_is_step_cost_usd():
    from genblaze_core.agents.loop import AgentResult
    from genblaze_core.models.step import Step
    from genblaze_core.testing import MockProvider

    assert "cost_usd" in Step.model_fields
    assert "cost_usd" in inspect.signature(MockProvider.__init__).parameters
    assert "total_cost_usd" in _field_names(AgentResult)
    # spec's "CostLedger" does not exist
    assert not hasattr(genblaze_core, "CostLedger")


# --- #5 object-lock params ---------------------------------------------------
def test_sdkchk05_object_lock_params():
    import typing

    from genblaze_core.storage.base import ObjectLockConfig, ObjectLockMode
    from genblaze_core.storage.sink import ObjectStorageSink

    assert "manifest_lock" in inspect.signature(ObjectStorageSink.__init__).parameters
    olc = inspect.signature(ObjectLockConfig.__init__)
    assert "retain_until" in olc.parameters and "mode" in olc.parameters
    # ObjectLockMode is a Literal, not an Enum
    assert set(typing.get_args(ObjectLockMode)) == {"GOVERNANCE", "COMPLIANCE"}


# --- #6 webhook sink shape ---------------------------------------------------
def test_sdkchk06_webhook_config_shape():
    from genblaze_core.webhooks.sink import WebhookConfig, WebhookSink

    params = set(inspect.signature(WebhookConfig.__init__).parameters)
    for f in ("url", "headers", "timeout", "max_retries", "include_events"):
        assert f in params
    assert "config" in inspect.signature(WebhookSink.__init__).parameters


# --- #7 B2 event notification is a PLATFORM surface, not a pip receiver -------
def test_sdkchk07_no_builtin_webhook_receiver():
    # genblaze ships a webhook *sender* (WebhookSink); receiving + HMAC verifying
    # B2 Event Notifications (hmacSha256SigningSecret) is ours to build in P3.
    import genblaze_core.webhooks as wh

    names = dir(wh)
    assert "WebhookSink" in names or hasattr(wh, "sink")
    assert not any("receiver" in n.lower() for n in names)


# --- #8 StorageBackend interface --------------------------------------------
def test_sdkchk08_storagebackend_abstract_set():
    from genblaze_core.storage.base import StorageBackend

    assert StorageBackend.__abstractmethods__ == frozenset(
        {"put", "get", "exists", "delete", "get_url", "get_durable_url"}
    )
    # list() has no default impl (raises NotImplementedError) -> we override it
    assert "list" not in StorageBackend.__abstractmethods__


# --- #9 conformance kit ------------------------------------------------------
def test_sdkchk09_conformance_harness_present():
    from genblaze_core.testing import ProviderComplianceTests

    assert inspect.isclass(ProviderComplianceTests)
    assert "make_provider" in ProviderComplianceTests.__abstractmethods__


# --- deviations the spec assumed but the SDK does not ship -------------------
def test_no_failing_or_modelerror_provider_classes():
    import genblaze_core.testing as t

    assert not hasattr(t, "FailingProvider")
    assert not hasattr(t, "ModelErrorProvider")
    # the real primitive:
    assert "should_fail" in inspect.signature(t.MockProvider.__init__).parameters


def test_no_genblaze_cli_console_script():
    import importlib.metadata as md

    scripts = [
        ep.name
        for ep in md.entry_points(group="console_scripts")
        if ep.name == "genblaze"
    ]
    assert scripts == []  # no `genblaze` CLI ships; we verify via the Python API


def test_mp3_embedding_requires_mutagen_and_it_is_present():
    import mutagen  # noqa: F401
    from genblaze_core.media import get_handler

    assert type(get_handler("audio/mpeg")).__name__ == "Mp3Handler"
    assert type(get_handler("audio/wav")).__name__ == "WavHandler"
