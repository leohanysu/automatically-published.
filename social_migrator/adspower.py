from dataclasses import dataclass


@dataclass
class AdsPowerLifecycle:
    client: object
    profile_id: str

    def open_foreground_verified(self) -> dict:
        port = self.client.start_profile(self.profile_id)
        self.client.bring_to_front(self.profile_id)
        viewport = self.client.viewport(self.profile_id)
        if not viewport.get("visible"):
            raise RuntimeError("AdsPower 窗口不可见，已停止自动发布")
        return {"profile_id": self.profile_id, "cdp_port": port, "viewport": viewport}

    def force_recover(self) -> dict:
        self.client.stop_profile_tree(self.profile_id)
        return self.open_foreground_verified()
