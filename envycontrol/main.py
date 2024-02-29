
import argparse
import logging
import sys

from envycontrol import SDDM_XSETUP_CONTENT, SDDM_XSETUP_PATH, VERSION
from envycontrol.cacheconfig import CachedConfig
from envycontrol.utils import (assert_root, cleanup, create_file,
                               get_current_mode, graphics_mode_switcher,
                               rebuild_initramfs)

SUPPORTED_OPTIMUS_MODES = ['integrated', 'hybrid', 'nvidia']
SUPPORTED_DISPLAY_MANAGERS = ['gdm', 'gdm3', 'sddm', 'lightdm']
RTD3_MODES = [0, 1, 2, 3]


def main():
    # define CLI arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action='version', version=VERSION,
                        help='Output the current version')
    parser.add_argument('-q', '--query', action='store_true',
                        help='Query the current graphics mode')
    parser.add_argument('-s', '--switch', type=str, metavar='MODE', action='store', choices=SUPPORTED_OPTIMUS_MODES,
                        help='Switch the graphics mode. Available choices: %(choices)s')
    parser.add_argument('--dm', type=str, metavar='DISPLAY_MANAGER', action='store', choices=SUPPORTED_DISPLAY_MANAGERS,
                        help='Manually specify your Display Manager for Nvidia mode. Available choices: %(choices)s')
    parser.add_argument('--force-comp', action='store_true',
                        help='Enable ForceCompositionPipeline on Nvidia mode')
    parser.add_argument('--coolbits', type=int, nargs='?', metavar='VALUE', action='store', const=28,
                        help='Enable Coolbits on Nvidia mode. Default if specified: %(const)s')
    parser.add_argument('--rtd3', type=int, nargs='?', metavar='VALUE', action='store', choices=RTD3_MODES, const=2,
                        help='Setup PCI-Express Runtime D3 (RTD3) Power Management on Hybrid mode. Available choices: %(choices)s. Default if specified: %(const)s')
    parser.add_argument('--use-nvidia-current', action='store_true',
                        help='Use nvidia-current instead of nvidia for kernel modules')
    parser.add_argument('--reset-sddm', action='store_true',
                        help='Restore default Xsetup file')
    parser.add_argument('--reset', action='store_true',
                        help='Revert changes made by EnvyControl')
    parser.add_argument('--cache-create', action='store_true',
                        help='Create cache used by EnvyControl; only works in hybrid mode')
    parser.add_argument('--cache-delete', action='store_true',
                        help='Delete cache created by EnvyControl')
    parser.add_argument('--cache-query', action='store_true',
                        help='Show cache created by EnvyControl')
    parser.add_argument('--verbose', default=False, action='store_true',
                        help='Enable verbose mode')

    # print help if no arg is provided
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    # log formatting
    logging.basicConfig(format='%(levelname)s: %(message)s')

    # set debug level for verbose mode
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.query:
        mode = get_current_mode()
        print(mode)
        return
    elif args.cache_create:
        assert_root()
        CachedConfig(args).create_cache_file()
        return
    elif args.cache_delete:
        assert_root()
        CachedConfig.delete_cache_file()
        return
    elif args.cache_query:
        CachedConfig.show_cache_file()
        return

    if args.switch or args.reset_sddm or args.reset:
        with CachedConfig(args).adapter() as adapter:
            if args.switch:
                assert_root()
                graphics_mode_switcher(**vars(adapter.app_args))
            elif args.reset_sddm:
                assert_root()
                create_file(SDDM_XSETUP_PATH, SDDM_XSETUP_CONTENT, True)
                print('Operation completed successfully')
            elif args.reset:
                assert_root()
                cleanup()
                CachedConfig.delete_cache_file()
                rebuild_initramfs()
                print('Operation completed successfully')
