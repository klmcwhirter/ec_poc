
import logging
import os
import re
import subprocess
import sys

from envycontrol import (BLACKLIST_CONTENT, BLACKLIST_PATH, COOLBITS,
                         EXTRA_XORG_90_PATH, EXTRA_XORG_CONTENT,
                         EXTRA_XORG_PATH, FORCE_COMP, LIGHTDM_CONFIG_CONTENT,
                         LIGHTDM_CONFIG_PATH, LIGHTDM_SCRIPT_PATH,
                         MODESET_CONTENT, MODESET_CURRENT_CONTENT,
                         MODESET_CURRENT_RTD3, MODESET_PATH, MODESET_RTD3,
                         NVIDIA_XRANDR_SCRIPT, SDDM_XSETUP_PATH,
                         UDEV_INTEGRATED, UDEV_INTEGRATED_PATH,
                         UDEV_PM_CONTENT, UDEV_PM_PATH, XORG_AMD, XORG_INTEL,
                         XORG_PATH)


def graphics_mode_switcher(*, switch, dm, force_comp, coolbits, rtd3, use_nvidia_current, **kwargs):
    print(f"Switching to {switch} mode")

    if switch == 'integrated':

        if logging.getLogger().level == logging.DEBUG:
            service = subprocess.run(
                ["systemctl", "disable", "nvidia-persistenced.service"])
        else:
            service = subprocess.run(
                ["systemctl", "disable", "nvidia-persistenced.service"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if service.returncode == 0:
            print('Successfully disabled nvidia-persistenced.service')
        else:
            logging.error("An error ocurred while disabling service")

        cleanup()

        # blacklist all nouveau and Nvidia modules
        create_file(BLACKLIST_PATH, BLACKLIST_CONTENT)

        # power off the Nvidia GPU with udev rules
        create_file(UDEV_INTEGRATED_PATH, UDEV_INTEGRATED)

    elif switch == 'hybrid':
        print(f"Enable PCI-Express Runtime D3 (RTD3) Power Management: {rtd3 or False}")
        cleanup()

        if logging.getLogger().level == logging.DEBUG:
            service = subprocess.run(
                ["systemctl", "enable", "nvidia-persistenced.service"])
        else:
            service = subprocess.run(
                ["systemctl", "enable", "nvidia-persistenced.service"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if service.returncode == 0:
            print('Successfully enabled nvidia-persistenced.service')
        else:
            logging.error("An error ocurred while enabling service")

        if rtd3 == None:
            if use_nvidia_current:
                create_file(MODESET_PATH, MODESET_CURRENT_CONTENT)
            else:
                create_file(MODESET_PATH, MODESET_CONTENT)
        else:
            # setup rtd3
            if use_nvidia_current:
                create_file(
                    MODESET_PATH, MODESET_CURRENT_RTD3.format(rtd3))
            else:
                create_file(MODESET_PATH, MODESET_RTD3.format(rtd3))
            create_file(UDEV_PM_PATH, UDEV_PM_CONTENT)

    elif switch == 'nvidia':
        print(f"Enable ForceCompositionPipeline: {force_comp}")
        print(f"Enable Coolbits: {coolbits or False}")

        if logging.getLogger().level == logging.DEBUG:
            service = subprocess.run(
                ["systemctl", "enable", "nvidia-persistenced.service"])
        else:
            service = subprocess.run(
                ["systemctl", "enable", "nvidia-persistenced.service"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if service.returncode == 0:
            print('Successfully enabled nvidia-persistenced.service')
        else:
            logging.error("An error ocurred while enabling service")

        cleanup()
        # get the Nvidia dGPU PCI bus
        nvidia_gpu_pci_bus = get_nvidia_gpu_pci_bus()

        # get iGPU vendor
        igpu_vendor = get_igpu_vendor()

        # create the X.org config
        if igpu_vendor == 'intel':
            create_file(XORG_PATH, XORG_INTEL.format(nvidia_gpu_pci_bus))
        elif igpu_vendor == 'amd':
            create_file(XORG_PATH, XORG_AMD.format(nvidia_gpu_pci_bus))

        # enable modeset for Nvidia driver
        if use_nvidia_current:
            create_file(MODESET_PATH, MODESET_CURRENT_CONTENT)
        else:
            create_file(MODESET_PATH, MODESET_CONTENT)

        # extra Xorg config
        if force_comp and coolbits != None:
            create_file(EXTRA_XORG_PATH, EXTRA_XORG_CONTENT + FORCE_COMP +
                        COOLBITS.format(coolbits) + 'EndSection\n')
        elif force_comp:
            create_file(EXTRA_XORG_PATH, EXTRA_XORG_CONTENT +
                        FORCE_COMP + 'EndSection\n')
        elif coolbits != None:
            create_file(EXTRA_XORG_PATH, EXTRA_XORG_CONTENT +
                        COOLBITS.format(coolbits) + 'EndSection\n')

        # try to detect the display manager if not provided
        if dm == None:
            display_manager = get_display_manager()
        else:
            display_manager = dm

        # only sddm and lightdm require further config
        if display_manager == 'sddm':
            # backup Xsetup
            if os.path.exists(SDDM_XSETUP_PATH):
                logging.info("Creating Xsetup backup")
                with open(SDDM_XSETUP_PATH, mode='r', encoding='utf-8') as f:
                    create_file(SDDM_XSETUP_PATH+'.bak', f.read())
            create_file(SDDM_XSETUP_PATH,
                        generate_xrandr_script(igpu_vendor), True)
        elif display_manager == 'lightdm':
            create_file(LIGHTDM_SCRIPT_PATH,
                        generate_xrandr_script(igpu_vendor), True)
            create_file(LIGHTDM_CONFIG_PATH, LIGHTDM_CONFIG_CONTENT)

    # rebuild_initramfs()
    print('Operation completed successfully')
    print('Please reboot your computer for changes to take effect!')


def cleanup():
    # define list of files to remove
    to_remove = [
        BLACKLIST_PATH,
        UDEV_INTEGRATED_PATH,
        UDEV_PM_PATH,
        XORG_PATH,
        EXTRA_XORG_PATH,
        EXTRA_XORG_90_PATH,
        MODESET_PATH,
        LIGHTDM_SCRIPT_PATH,
        LIGHTDM_CONFIG_PATH,
    ]

    # remove each file in the list
    for file_path in to_remove:
        try:
            os.remove(file_path)
            logging.info(f"Removed file {file_path}")
        except OSError as e:
            # only warn if file exists (code 2)
            if e.errno != 2:
                logging.error(f"Failed to remove file '{file_path}': {e}")

    # restore Xsetup backup if found
    backup_path = SDDM_XSETUP_PATH + ".bak"
    if os.path.exists(backup_path):
        logging.info("Restoring Xsetup backup")
        with open(backup_path, mode="r", encoding="utf-8") as f:
            create_file(SDDM_XSETUP_PATH, f.read())
        # remove backup
        os.remove(backup_path)
        logging.info(f"Removed file {backup_path}")


def get_nvidia_gpu_pci_bus():
    lspci_output = subprocess.check_output(['lspci']).decode('utf-8')
    for line in lspci_output.splitlines():
        if 'NVIDIA' in line and ('VGA compatible controller' in line or '3D controller' in line):
            # remove leading zeros
            pci_bus_id = line.split()[0].replace("0000:", "")
            logging.info(f"Found Nvidia GPU at {pci_bus_id}")
            break
    else:
        logging.error("Could not find Nvidia GPU")
        print("Try switching to hybrid mode first!")
        sys.exit(1)

    # need to return the BusID in 'PCI:bus:device:function' format
    # also perform hexadecimal to decimal conversion
    bus, device_function = pci_bus_id.split(":")
    device, function = device_function.split(".")
    return f"PCI:{int(bus, 16)}:{int(device, 16)}:{int(function, 16)}"


def get_igpu_vendor():
    lspci_output = subprocess.check_output(["lspci"]).decode('utf-8')
    for line in lspci_output.splitlines():
        if 'VGA compatible controller' in line or 'Display controller' in line:
            if 'Intel' in line:
                logging.info("Found Intel iGPU")
                return 'intel'
            elif 'ATI' in line or 'AMD' in line or 'AMD/ATI' in line:
                logging.info("Found AMD iGPU")
                return 'amd'
    logging.warning("Could not find Intel or AMD iGPU")
    return None


def get_display_manager():
    try:
        with open('/etc/systemd/system/display-manager.service', 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'ExecStart=(.+)\n', content)
            if match:
                # only return the final component of the path
                display_manager = os.path.basename(match.group(1))
                logging.info(f"Found {display_manager} Display Manager")
                return display_manager
    except FileNotFoundError:
        logging.warning("Display Manager detection is not available")


def generate_xrandr_script(igpu_vendor):
    if igpu_vendor == 'intel':
        return NVIDIA_XRANDR_SCRIPT.format('modesetting')
    elif igpu_vendor == 'amd':
        amd_igpu_name = get_amd_igpu_name()
        if amd_igpu_name != None:
            return NVIDIA_XRANDR_SCRIPT.format(amd_igpu_name)
        else:
            return NVIDIA_XRANDR_SCRIPT.format('modesetting')
    else:
        return NVIDIA_XRANDR_SCRIPT.format('modesetting')


def get_amd_igpu_name():
    if not os.path.exists('/usr/bin/xrandr'):
        logging.warning("The 'xrandr' command is not available. Make sure the package is installed!")
        return None

    try:
        xrandr_output = subprocess.check_output(
            ['xrandr', '--listproviders']).decode('utf-8')
    except subprocess.CalledProcessError:
        logging.warning(
            "Failed to run the 'xrandr' command.")

    pattern = re.compile(r'(name:).*(ATI*|AMD*|AMD\/ATI)*')

    if pattern.findall(xrandr_output):
        return re.search(pattern, xrandr_output).group(0)[5:]
    else:
        logging.warning(
            "Could not find AMD iGPU in 'xrandr' output.")
        return None


def rebuild_initramfs():
    # Debian and Ubuntu derivatives
    if os.path.exists('/etc/debian_version'):
        command = ['update-initramfs', '-u', '-k', 'all']
    # RHEL and SUSE derivatives
    elif os.path.exists('/etc/redhat-release') or os.path.exists('/usr/bin/zypper'):
        command = ['dracut', '--force', '--regenerate-all']
    # EndeavourOS with dracut
    elif os.path.exists('/usr/lib/endeavouros-release') and os.path.exists('/usr/bin/dracut'):
        command = ['dracut-rebuild']
    else:
        command = []

    if len(command) != 0:
        print('Rebuilding the initramfs...')
        if logging.getLogger().level == logging.DEBUG:
            p = subprocess.run(command)
        else:
            p = subprocess.run(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if p.returncode == 0:
            print('Successfully rebuilt the initramfs!')
        else:
            logging.error("An error ocurred while rebuilding the initramfs")


def create_file(path, content, executable=False):
    try:
        # create the parent folders if needed
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode='w', encoding='utf-8') as f:
            f.write(content)
        logging.info(f"Created file {path}")
        if logging.getLogger().level == logging.DEBUG:
            print(content)

        # add execution privilege
        if executable:
            subprocess.run(['chmod', '+x', path], stdout=subprocess.DEVNULL)
            logging.info(f"Added execution privilege to file {path}")
    except OSError as e:
        logging.error(f"Failed to create file '{path}': {e}")


def assert_root():
    if os.geteuid() != 0:
        logging.error("This operation requires root privileges")
        sys.exit(1)


def get_current_mode():
    mode = 'hybrid'
    if os.path.exists(BLACKLIST_PATH) and os.path.exists(UDEV_INTEGRATED_PATH):
        mode = 'integrated'
    elif os.path.exists(XORG_PATH) and os.path.exists(MODESET_PATH):
        mode = 'nvidia'
    return mode


def get_igpu_bus_pci_bus():
    lines = get_lspci_lines()
    rc = None
    for line in lines:
        if 'Intel' in line:
            pci_bus_id = line.split()[0].replace("0000:", "")

            # need to return the BusID in 'PCI:bus:device:function' format
            # also perform hexadecimal to decimal conversion
            bus, device_function = pci_bus_id.split(":")
            device, function = device_function.split(".")

            rc = f"PCI:{int(bus, 16)}:{int(device, 16)}:{int(function, 16)}"
    return rc


def get_lspci_lines():
    lspci_output = subprocess.check_output(["lspci"]).decode('utf-8')
    lines = [line for line in lspci_output.splitlines()
             if 'VGA compatible controller' in line or 'Display controller' in line]
    return lines
