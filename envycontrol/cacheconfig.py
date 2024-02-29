
import os
from contextlib import contextmanager

from envycontrol import PREFIX
from envycontrol.utils import (get_amd_igpu_name, get_current_mode,
                               get_display_manager, get_igpu_bus_pci_bus,
                               get_igpu_vendor)

# Note: Do NOT remove this in cleanup!
CACHE_FILE_PATH = PREFIX + '/var/cache/envycontrol/cache.json'


class CachedConfig:
    '''Adapter for config from CACHE_FILE_PATH'''

    def __init__(self, app_args) -> None:
        self.app_args = app_args
        self.current_mode = get_current_mode()

    @contextmanager
    def adapter(self):
        global get_nvidia_gpu_pci_bus
        use_cache = os.path.exists(CACHE_FILE_PATH)

        if use_cache:
            self.read_cache_file()  # might not be in hybrid mode

            # rebind function to use cached value instead of detection
            get_nvidia_gpu_pci_bus = self.get_nvidia_gpu_pci_bus

        if self.is_hybrid():  # recreate cache file when in hybrid mode
            self.create_cache_file()

        yield self  # back to main ...

    def create_cache_file(self):
        if not self.is_hybrid():
            raise ValueError('--cache-create requires that the system be in the hybrid Optimus mode')

        self.nvidia_gpu_pci_bus = get_nvidia_gpu_pci_bus()
        self.obj = self.create_cache_obj(self.nvidia_gpu_pci_bus)
        self.write_cache_file()

    def create_cache_obj(self, nvidia_gpu_pci_bus):
        from datetime import datetime
        return {
            'switch': {
                'nvidia_gpu_pci_bus': nvidia_gpu_pci_bus
            },
            'metadata': {
                'audit_iso_tmstmp': datetime.now().isoformat(),
                'args': vars(self.app_args),
                'amd_igpu_name': get_amd_igpu_name(),
                'current_mode': self.current_mode,
                'display_manager': get_display_manager(),
                'igpu_pci_bus': get_igpu_bus_pci_bus(),
                'igpu_vendor': get_igpu_vendor(),
            }
        }

    def is_hybrid(self):
        return 'hybrid' == self.current_mode

    def get_nvidia_gpu_pci_bus(self):
        return self.nvidia_gpu_pci_bus

    def get_metadata(self):
        return self.obj['metadata']

    @staticmethod
    def delete_cache_file():
        os.remove(CACHE_FILE_PATH)
        os.removedirs(os.path.dirname(CACHE_FILE_PATH))

    def read_cache_file(self):
        from json import loads
        if os.path.exists(CACHE_FILE_PATH):
            with open(CACHE_FILE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
            self.obj = loads(content)
            self.nvidia_gpu_pci_bus = self.obj['switch']['nvidia_gpu_pci_bus']
        elif self.is_hybrid():
            self.nvidia_gpu_pci_bus = get_nvidia_gpu_pci_bus()
        else:
            raise ValueError('No cache present. Operation requires that the system be in the hybrid Optimus mode')

    @staticmethod
    def show_cache_file():
        content = f'ERROR: Could not read {CACHE_FILE_PATH}'
        if os.path.exists(CACHE_FILE_PATH):
            with open(CACHE_FILE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
        print(content)

    def write_cache_file(self):
        from json import dump
        os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)

        with open(CACHE_FILE_PATH, 'w', encoding='utf-8') as f:
            dump(self.obj, fp=f, indent=4, sort_keys=False)
