# -*- coding: utf-8 -*-
import os
import json

CONFIG_FILE = "machine_config.json"

_default_cfg = {
    "api_url": os.environ.get("BOTTLE_API_URL", "http://localhost/server/api"),
    "machine_id": os.environ.get("MACHINE_ID", "1001"),
    "serial_number": "0000000",
    "machine_type": "point"
}

def load_machine_config():
    cfg = dict(_default_cfg)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                disk_cfg = json.load(f)
                cfg.update(disk_cfg)
        except Exception as ex:
            print(f"[Config] Error loading {CONFIG_FILE}: {ex}")
    return cfg

def save_machine_config(cfg_updates):
    current = load_machine_config()
    current.update(cfg_updates)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
    except Exception as ex:
        print(f"[Config] Error saving {CONFIG_FILE}: {ex}")
    return current

def get_api_base():
    cfg = load_machine_config()
    return os.environ.get("BOTTLE_API_URL", cfg.get("api_url", _default_cfg["api_url"])).rstrip("/")

def get_machine_id():
    cfg = load_machine_config()
    return str(os.environ.get("MACHINE_ID", cfg.get("machine_id", _default_cfg["machine_id"]))).strip()

def get_machine_type():
    cfg = load_machine_config()
    return cfg.get("machine_type", _default_cfg["machine_type"])
