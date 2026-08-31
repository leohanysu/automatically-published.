import json
from pathlib import Path


REQUIRED_PERMISSIONS = {
    "base.read", "table.read", "field.read", "record.read", "record.write", "attachment.upload"
}


def load_manifest(path: str | Path = "templates/feishu/template-manifest.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_permissions(granted: set[str]) -> dict:
    missing = sorted(REQUIRED_PERMISSIONS - set(granted))
    return {"ok": not missing, "missing": missing}


def verify_schema(schema: dict, manifest: dict | None = None) -> dict:
    manifest = manifest or load_manifest()
    expected = {f["name"]: f["type"] for f in manifest["tables"][0]["fields"]}
    actual = {f["name"]: f.get("type") for f in schema.get("fields", [])}
    missing = sorted(name for name in expected if name not in actual)
    wrong_type = sorted(name for name in expected if name in actual and expected[name] != actual[name])
    return {"ok": not missing and not wrong_type, "missing": missing, "wrong_type": wrong_type}


class FeishuProvisioner:
    """Deterministic orchestration boundary; network adapter is injected by caller."""

    def __init__(self, client, manifest: dict | None = None):
        self.client = client
        self.manifest = manifest or load_manifest()

    def provision(self) -> dict:
        permissions = check_permissions(set(self.client.permissions()))
        if not permissions["ok"]:
            return {"ok": False, "stage": "permissions", **permissions}
        if hasattr(self.client, "copy_template"):
            base = self.client.copy_template(self.manifest)
            method = "official_copy"
        else:
            base = self.client.rebuild_from_manifest(self.manifest)
            method = "manifest_rebuild"
        verification = verify_schema(self.client.get_schema(base), self.manifest)
        return {"ok": verification["ok"], "base": base, "method": method, "verification": verification}
