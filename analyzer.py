import os
import subprocess
import json
import shlex
import shutil
import time
import threading
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_cmd(cmd, timeout=5):
    try:
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return res.stdout.strip(), res.returncode
    except Exception:
        return "", -1

def get_os_info():
    info = {"id": "unknown", "name": "Unknown Linux"}
    try:
        values = {}
        with open("/etc/os-release", "r") as release_file:
            for line in release_file:
                key, separator, value = line.partition("=")
                if separator:
                    values[key] = value.strip().strip('"')
        info["id"] = values.get("ID", "unknown")
        info["name"] = values.get("PRETTY_NAME", values.get("NAME", info["id"]))
    except Exception:
        pass
    return info


PACKAGE_MANAGER_DEFINITIONS = {
    "pacman": {
        "query": "pacman -Qq {package}",
        "search": "pacman -Si {package}",
        "install": "sudo pacman -S --needed {packages}",
        "orphaned": "pacman -Qtdq",
    },
    "apt": {
        "query": "dpkg-query -W -f='${{Status}}' {package} 2>/dev/null | grep -q 'install ok installed'",
        "search": "apt-cache show {package}",
        "install": "sudo apt-get install -y {packages}",
    },
    "dnf": {
        "query": "rpm -q {package}",
        "search": "dnf info {package}",
        "install": "sudo dnf install -y {packages}",
    },
    "yum": {
        "query": "rpm -q {package}",
        "search": "yum info {package}",
        "install": "sudo yum install -y {packages}",
    },
    "zypper": {
        "query": "rpm -q {package}",
        "search": "zypper --non-interactive info {package}",
        "install": "sudo zypper --non-interactive install {packages}",
    },
    "apk": {
        "query": "apk info -e {package}",
        "search": "apk info {package}",
        "install": "sudo apk add {packages}",
    },
    "xbps": {
        "query": "xbps-query -l {package}",
        "search": "xbps-query -Rs {package}",
        "install": "sudo xbps-install -y {packages}",
    },
}


PACKAGE_NAME_ALIASES = {
    "apt": {
        "mesa": "mesa-vulkan-drivers",
        "intel-media-driver": "intel-media-va-driver",
        "libva-intel-driver": "intel-media-va-driver",
        "libva-mesa-driver": "mesa-vulkan-drivers",
        "nvidia": "nvidia-driver",
    },
    "dnf": {"libva-mesa-driver": "mesa-va-drivers", "nvidia": "akmod-nvidia", "nvidia-utils": "xorg-x11-drv-nvidia-libs"},
    "yum": {"libva-mesa-driver": "mesa-va-drivers", "nvidia": "akmod-nvidia", "nvidia-utils": "xorg-x11-drv-nvidia-libs"},
    "zypper": {"libva-mesa-driver": "Mesa-libva", "nvidia": "x11-video-nvidiaG06", "nvidia-utils": "nvidia-compute-G06"},
}


def detect_package_manager():
    for manager in ("pacman", "apt", "dnf", "yum", "zypper", "apk", "xbps"):
        executable = "apt-get" if manager == "apt" else manager
        if shutil.which(executable):
            return manager
    return None


def package_name(pkg_name, manager=None):
    manager = manager or detect_package_manager()
    return PACKAGE_NAME_ALIASES.get(manager, {}).get(pkg_name, pkg_name)


def package_command(manager, action, packages):
    definition = PACKAGE_MANAGER_DEFINITIONS.get(manager)
    if not definition or action not in definition:
        return ""
    if isinstance(packages, str):
        packages = [packages]
    names = " ".join(shlex.quote(package_name(pkg, manager)) for pkg in packages)
    return definition[action].format(package=names, packages=names)


def check_package_installed(pkg_name, manager=None):
    manager = manager or detect_package_manager()
    if not manager:
        return False
    command = package_command(manager, "query", [pkg_name])
    _, code = run_cmd(command)
    return code == 0

def check_services_status(service_names):
    # Returns a dict of the form {name: {"active": bool, "enabled": bool}}
    statuses = {name: {"active": False, "enabled": False} for name in service_names}
    if not service_names:
        return statuses
    names = " ".join(shlex.quote(name) for name in service_names)
    active_out, _ = run_cmd(f"systemctl is-active {names} 2>/dev/null")
    enabled_out, _ = run_cmd(f"systemctl is-enabled {names} 2>/dev/null")
    active_lines = active_out.splitlines()
    enabled_lines = enabled_out.splitlines()
    for i, name in enumerate(service_names):
        if i < len(active_lines):
            statuses[name]["active"] = active_lines[i] == "active"
        if i < len(enabled_lines):
            statuses[name]["enabled"] = enabled_lines[i] == "enabled"
    return statuses

def check_service_status(service_name):
    status = check_services_status([service_name])[service_name]
    return status["active"], status["enabled"]


def format_size(size_bytes):
    value = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}"
        value /= 1024


def get_directory_size(path):
    if not os.path.isdir(path):
        return 0
    output, code = run_cmd(f"du -sb -- {shlex.quote(path)} 2>/dev/null", timeout=15)
    if code != 0 or not output:
        return 0
    try:
        return int(output.split()[0])
    except (ValueError, IndexError):
        return 0


def get_cleanup_recommendations(package_manager):
    recommendations = []
    user_cache = os.path.expanduser("~/.cache")
    user_cache_size = get_directory_size(user_cache)
    if user_cache_size:
        recommendations.append({
            "title": "Caché de aplicaciones del usuario",
            "description": f"Ocupa aproximadamente {format_size(user_cache_size)}. Cierra las aplicaciones antes de limpiarla.",
            "command": "find ~/.cache -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +",
            "severity": "low"
        })

    package_cache_paths = {
        "apt": "/var/cache/apt/archives",
        "pacman": "/var/cache/pacman/pkg",
        "dnf": "/var/cache/dnf",
        "yum": "/var/cache/yum",
        "zypper": "/var/cache/zypp",
        "apk": "/var/cache/apk",
    }
    package_cache = package_cache_paths.get(package_manager)
    package_cache_size = get_directory_size(package_cache) if package_cache else 0
    package_commands = {
        "apt": "sudo apt-get clean",
        "pacman": "sudo pacman -Sc --noconfirm",
        "dnf": "sudo dnf clean all",
        "yum": "sudo yum clean all",
        "zypper": "sudo zypper clean --all",
        "apk": "sudo apk cache clean",
        "xbps": "sudo xbps-remove -O",
    }
    if package_cache_size and package_manager in package_commands:
        recommendations.append({
            "title": "Caché del gestor de paquetes",
            "description": f"Ocupa aproximadamente {format_size(package_cache_size)} en {package_manager}.",
            "command": package_commands[package_manager],
            "severity": "low"
        })

    journal_size, journal_code = run_cmd("journalctl --disk-usage 2>/dev/null", timeout=10)
    if journal_code == 0 and journal_size:
        recommendations.append({
            "title": "Logs antiguos de systemd",
            "description": f"{journal_size}. Conserva los últimos 14 días y elimina los anteriores.",
            "command": "sudo journalctl --vacuum-time=14d",
            "severity": "low"
        })
    return recommendations


def launch_commands_terminal(commands, title):
    script_commands = [
        f"echo {shlex.quote('Laptop Analyzer: ' + title)}",
        *commands,
        "echo 'Proceso terminado.'",
        "read -r -p 'Presiona Enter para cerrar esta terminal...'",
    ]
    script = "set -e\n" + "\n".join(script_commands)
    terminal_commands = [
        ("gnome-terminal", ["gnome-terminal", "--", "bash", "-lc", script]),
        ("konsole", ["konsole", "-e", "bash", "-lc", script]),
        ("xfce4-terminal", ["xfce4-terminal", "--command", f"bash -lc {shlex.quote(script)}"]),
        ("kitty", ["kitty", "bash", "-lc", script]),
        ("alacritty", ["alacritty", "-e", "bash", "-lc", script]),
        ("x-terminal-emulator", ["x-terminal-emulator", "-e", "bash", "-lc", script]),
    ]
    for executable, command in terminal_commands:
        if shutil.which(executable):
            subprocess.Popen(command, start_new_session=True)
            return True
    return False


def launch_cleanup_terminal(package_manager):
    package_commands = {
        "apt": "sudo apt-get clean",
        "pacman": "sudo pacman -Sc --noconfirm",
        "dnf": "sudo dnf clean all",
        "yum": "sudo yum clean all",
        "zypper": "sudo zypper clean --all",
        "apk": "sudo apk cache clean",
        "xbps": "sudo xbps-remove -O",
    }
    commands = [
        "echo 'Laptop Analyzer: limpieza y mantenimiento del sistema'",
        "echo 'Cerrando caché de aplicaciones del usuario...'",
        "if [ -d ~/.cache ]; then find ~/.cache -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; fi",
    ]
    if package_manager in package_commands:
        commands.extend([
            f"echo 'Limpiando caché de {package_manager}...'",
            package_commands[package_manager],
        ])
    commands.extend([
        "echo 'Eliminando logs de systemd con más de 14 días...'",
        "sudo journalctl --vacuum-time=14d",
    ])
    return launch_commands_terminal(commands, "limpieza y mantenimiento del sistema")

def _package_search_ok(pkg_name, manager):
    _, code = run_cmd(package_command(manager, "search", [pkg_name]))
    return code == 0

def check_aur_packages(package_names):
    # Batch query the AUR RPC API (one HTTP request, up to 100 names per query)
    available = {}
    names = [name for name in package_names if name]
    if not names:
        return available
    for i in range(0, len(names), 100):
        chunk = names[i:i + 100]
        params = "&".join(f"arg[]={urllib.parse.quote(name)}" for name in chunk)
        url = f"https://aur.archlinux.org/rpc/?v=5&type=info&{params}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'LaptopAnalyzer/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
            for result in data.get("results", []):
                name = result.get("Name")
                if name:
                    available[name] = True
        except Exception:
            return available
    return available

def check_packages_installed(packages, manager=None, max_workers=8):
    manager = manager or detect_package_manager()
    results = {pkg: False for pkg in packages}
    if not manager:
        return results
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(check_package_installed, pkg, manager): pkg
            for pkg in packages
        }
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results

def check_packages_availability(packages, manager=None, max_workers=8):
    manager = manager or detect_package_manager()
    result = {pkg: "not_found" for pkg in packages}
    if not manager:
        return result
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        if manager == "pacman":
            # Official repositories (fast, local) then AUR in one batched request
            official = set()
            futures = {
                executor.submit(_package_search_ok, pkg, manager): pkg
                for pkg in packages
            }
            for future in as_completed(futures):
                if future.result():
                    official.add(futures[future])
            pending = [pkg for pkg in packages if pkg not in official]
            aur = check_aur_packages(pending)
            for pkg in packages:
                if pkg in official:
                    result[pkg] = "official"
                elif aur.get(pkg):
                    result[pkg] = "aur"
        else:
            futures = {
                executor.submit(_package_search_ok, pkg, manager): pkg
                for pkg in packages
            }
            for future in as_completed(futures):
                if future.result():
                    result[futures[future]] = "official"
    return result

def check_package_availability(pkg_name, manager=None):
    return check_packages_availability([pkg_name], manager).get(pkg_name, "not_found")

def check_aur_availability(pkg_name):
    return "aur" if check_aur_packages([pkg_name]).get(pkg_name) else "not_found"

def get_cpu_info():
    info = {"model": "Unknown CPU", "cores": 0, "governor": "unknown", "driver": "unknown", "temp": None}
    
    # Model and cores
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if "model name" in line:
                    info["model"] = line.split(":", 1)[1].strip()
                    break
        info["cores"] = os.cpu_count()
    except Exception:
        pass

    # Governor and Driver
    try:
        if os.path.exists("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"):
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "r") as f:
                info["governor"] = f.read().strip()
        if os.path.exists("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver"):
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver", "r") as f:
                info["driver"] = f.read().strip()
    except Exception:
        pass

    # Temperature (Tctl or package temperature, fallback to thermal zones)
    temp = None
    # Check thermal zones
    for zone in range(10):
        path = f"/sys/class/thermal/thermal_zone{zone}"
        if os.path.exists(path):
            try:
                with open(f"{path}/type", "r") as f:
                    tz_type = f.read().strip().lower()
                # prioritize cpu thermals
                if "cpu" in tz_type or "x86_pkg_temp" in tz_type:
                    with open(f"{path}/temp", "r") as f:
                        temp = int(f.read().strip()) / 1000.0
                        break
            except Exception:
                pass
    if temp is None:
        # Fallback to any thermal zone temp
        try:
            if os.path.exists("/sys/class/thermal/thermal_zone0/temp"):
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp = int(f.read().strip()) / 1000.0
        except Exception:
            pass
    info["temp"] = temp
    return info

def get_gpu_info():
    gpu_list = []
    # Run lspci to find GPUs
    out, _ = run_cmd("lspci -nn")
    for line in out.splitlines():
        if "VGA compatible controller" in line or "3D controller" in line:
            brand = "other"
            if "intel" in line.lower():
                brand = "intel"
            elif "nvidia" in line.lower():
                brand = "nvidia"
            elif "amd" in line.lower() or "ati" in line.lower():
                brand = "amd"
            gpu_list.append({
                "name": line.split(": ")[-1],
                "brand": brand,
                "raw": line
            })
    return gpu_list

def get_battery_info():
    info = {"present": False, "charge": 100, "health": 100, "status": "unknown", "power_draw": 0.0, "wear": 0.0}
    power_supply_dir = "/sys/class/power_supply"
    if not os.path.exists(power_supply_dir):
        return info
    
    bat_dirs = [d for d in os.listdir(power_supply_dir) if d.startswith("BAT")]
    if not bat_dirs:
        return info
    
    bat = bat_dirs[0]
    path = os.path.join(power_supply_dir, bat)
    info["present"] = True
    
    def read_val(filename):
        try:
            with open(os.path.join(path, filename), "r") as f:
                return f.read().strip()
        except:
            return None

    status = read_val("status")
    if status:
        info["status"] = status

    capacity = read_val("capacity")
    if capacity:
        try:
            info["charge"] = int(capacity)
        except:
            pass

    # Read energy or charge to determine health
    energy_full = read_val("energy_full") or read_val("charge_full")
    energy_full_design = read_val("energy_full_design") or read_val("charge_full_design")
    if energy_full and energy_full_design:
        try:
            full = float(energy_full)
            design = float(energy_full_design)
            if design > 0:
                health = (full / design) * 100.0
                info["health"] = min(100.0, round(health, 2))
                info["wear"] = max(0.0, round(100.0 - health, 2))
        except:
            pass

    power_now = read_val("power_now") or read_val("current_now")
    voltage_now = read_val("voltage_now")
    if power_now:
        try:
            # power_now is microwatts
            info["power_draw"] = round(float(power_now) / 1000000.0, 2)
        except:
            if voltage_now:
                try:
                    # current_now (microamperes) * voltage_now (microvolts) = microwatts
                    watts = (float(power_now) / 1000000.0) * (float(voltage_now) / 1000000.0)
                    info["power_draw"] = round(watts, 2)
                except:
                    pass
    return info

def read_meminfo():
    meminfo = {}
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    meminfo[parts[0].rstrip(":")] = int(parts[1])
    except Exception:
        pass
    return meminfo

def get_ram_info():
    meminfo = read_meminfo()
    total = meminfo.get("MemTotal", 0) * 1024
    available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0)) * 1024
    used = total - available
    percent = round((used / total) * 100, 1) if total else 0.0
    swap_total = meminfo.get("SwapTotal", 0) * 1024
    swap_free = meminfo.get("SwapFree", 0) * 1024
    swap_used = swap_total - swap_free
    swap_percent = round((swap_used / swap_total) * 100, 1) if swap_total else 0.0
    return {
        "total": total,
        "used": used,
        "available": available,
        "percent": percent,
        "swap_total": swap_total,
        "swap_used": swap_used,
        "swap_percent": swap_percent,
        "present": total > 0,
    }

def get_disk_info():
    disks = []
    try:
        block_dir = "/sys/block"
        skip_prefixes = ("loop", "ram", "zram", "dm-", "md", "sr", "fd")
        for name in sorted(os.listdir(block_dir)):
            if name.startswith(skip_prefixes):
                continue
            path = os.path.join(block_dir, name)

            def read_sys(relpath):
                try:
                    with open(os.path.join(path, relpath), "r") as f:
                        return f.read().strip()
                except Exception:
                    return None

            model = read_sys("device/model")
            if not model:
                model = read_sys("device/name") or name

            rotational = read_sys("queue/rotational")
            size_sectors = read_sys("size")

            if name.startswith("nvme"):
                disk_type = "nvme"
            elif rotational == "1":
                disk_type = "hdd"
            else:
                disk_type = "ssd"

            size = 0
            if size_sectors:
                try:
                    size = int(size_sectors) * 512
                except ValueError:
                    size = 0

            health = None
            if shutil.which("smartctl"):
                health_out, health_code = run_cmd(f"smartctl -H /dev/{name} 2>/dev/null", timeout=4)
                if health_code == 0:
                    for hline in health_out.splitlines():
                        if "PASSED" in hline:
                            health = "PASSED"
                            break
                        if "FAILED" in hline:
                            health = "FAILED"
                            break

            disks.append({
                "name": name,
                "model": model,
                "type": disk_type,
                "size": size,
                "health": health,
            })
    except Exception:
        pass
    return disks

def get_filesystem_usage():
    usage = []
    out, code = run_cmd("df -B1 -x tmpfs -x devtmpfs -x squashfs -x overlay -x proc -x sysfs -x cgroup -x cgroup2 2>/dev/null")
    if code != 0:
        return usage
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            total = int(parts[1])
            used = int(parts[2])
            percent = int(parts[4].rstrip("%"))
        except ValueError:
            continue
        usage.append({
            "mount": parts[5] if len(parts) > 5 else parts[0],
            "device": parts[0],
            "total": total,
            "used": used,
            "percent": percent,
        })
    return usage

_cpu_sample = None
_disk_sample = None
_cpu_lock = threading.Lock()
_disk_lock = threading.Lock()
_last_cpu_usage = 0.0

def _read_cpu_times():
    try:
        with open("/proc/stat", "r") as f:
            fields = f.readline().split()[1:]
        fields = [int(x) for x in fields]
        idle = fields[3] + fields[4]
        total = sum(fields)
        return idle, total
    except Exception:
        return 0, 0

def get_cpu_usage():
    global _cpu_sample, _last_cpu_usage
    with _cpu_lock:
        idle, total = _read_cpu_times()
        now = time.time()
        if _cpu_sample is None:
            _cpu_sample = (idle, total, now)
            time.sleep(0.3)
            idle, total = _read_cpu_times()
            now = time.time()
        prev_idle, prev_total, prev_time = _cpu_sample
        _cpu_sample = (idle, total, now)
        delta_total = total - prev_total
        elapsed = now - prev_time
        if delta_total <= 0 or elapsed < 0.2:
            # Sample too close together: return the last stable value to avoid noise
            return _last_cpu_usage
        delta_idle = idle - prev_idle
        _last_cpu_usage = round(max(0.0, min(100.0, 100.0 * (1 - delta_idle / delta_total))), 1)
        return _last_cpu_usage

def _read_disk_stats():
    stats = {}
    try:
        with open("/proc/diskstats", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 14:
                    continue
                name = parts[2]
                if name.startswith(("loop", "ram", "zram", "dm-", "md")):
                    continue
                stats[name] = (int(parts[5]), int(parts[9]))
    except Exception:
        pass
    return stats

def get_disk_io_rates():
    global _disk_sample
    with _disk_lock:
        now = time.time()
        current = _read_disk_stats()
        if _disk_sample is None:
            _disk_sample = (now, current)
            time.sleep(0.3)
            now = time.time()
            current = _read_disk_stats()
        prev_time, prev = _disk_sample
        _disk_sample = (now, current)
        elapsed = max(now - prev_time, 0.1)
        read_bytes = 0
        write_bytes = 0
        for name in set(prev.keys()) | set(current.keys()):
            cur_read, cur_write = current.get(name, (0, 0))
            prev_read, prev_write = prev.get(name, (0, 0))
            read_bytes += max(cur_read - prev_read, 0) * 512
            write_bytes += max(cur_write - prev_write, 0) * 512
        return round(read_bytes / elapsed), round(write_bytes / elapsed)

def get_top_processes():
    top_cpu = []
    top_mem = []
    out, _ = run_cmd("ps -eo comm,%cpu,%mem --sort=-%cpu 2>/dev/null | head -n 7")
    for line in out.splitlines()[1:]:
        parts = line.rsplit(None, 2)
        if len(parts) == 3:
            top_cpu.append({"name": parts[0], "cpu": parts[1], "mem": parts[2]})
    out, _ = run_cmd("ps -eo comm,%cpu,%mem --sort=-%mem 2>/dev/null | head -n 7")
    for line in out.splitlines()[1:]:
        parts = line.rsplit(None, 2)
        if len(parts) == 3:
            top_mem.append({"name": parts[0], "cpu": parts[1], "mem": parts[2]})
    return {"cpu": top_cpu, "memory": top_mem}

def get_live_stats():
    fs_usage = get_filesystem_usage()
    root_percent = 0.0
    for item in fs_usage:
        if item["mount"] == "/":
            root_percent = item["percent"]
            break
    read_speed, write_speed = get_disk_io_rates()
    return {
        "cpu": {"usage": get_cpu_usage()},
        "memory": get_ram_info(),
        "disk": {
            "read_speed": read_speed,
            "write_speed": write_speed,
            "usage_percent": root_percent,
        },
        "processes": get_top_processes(),
        "timestamp": time.time(),
    }

def perform_scan():
    cpu = get_cpu_info()
    gpus = get_gpu_info()
    battery = get_battery_info()
    os_info = get_os_info()
    package_manager = detect_package_manager()
    cleanup_recommendations = get_cleanup_recommendations(package_manager)
    
    # Check general performance helper packages
    packages_to_check = {
        "tlp": "Power management tool for laptops",
        "power-profiles-daemon": "Power profiles handling over D-Bus (default in GNOME/KDE)",
        "auto-cpufreq": "Automatic CPU speed & power optimizer for Linux",
        "thermald": "Intel Thermal Daemon to prevent overheating",
        "powertop": "Analyze power consumption",
        "irqbalance": "Balances interrupts across CPU cores",
        "reflector": "Retrieves latest Arch pacman mirrorlist",
        "pacman-contrib": "Utilities for pacman (e.g. paccache)",
        "mesa": "Open-source OpenGL/Vulkan implementation",
        "intel-media-driver": "VA-API driver for Intel Broadwell and newer GPUs",
        "libva-intel-driver": "VA-API driver for older Intel GPUs",
        "libva-mesa-driver": "VA-API driver for AMD GPUs",
        "nvidia": "NVIDIA proprietary graphics driver",
        "nvidia-utils": "NVIDIA driver utilities",
        "yay": "Yet another yogurt - AUR Helper",
        "paru": "Feature-rich AUR helper",
    }

    if package_manager != "pacman":
        for package in ["reflector", "pacman-contrib", "yay", "paru"]:
            packages_to_check.pop(package, None)

    installed = check_packages_installed(list(packages_to_check.keys()), package_manager)
    package_status = {
        pkg: {
            "installed": installed.get(pkg, False),
            "description": packages_to_check[pkg]
        }
        for pkg in packages_to_check
    }

    # Analyze active configurations & issues
    issues = []
    recommendations = []

    # 1. CPU Power profiles check
    has_power_daemon = package_status["power-profiles-daemon"]["installed"]
    has_tlp = package_status["tlp"]["installed"]
    has_auto_cpufreq = package_status["auto-cpufreq"]["installed"]

    active_daemons = []
    services_to_check = []
    if has_power_daemon:
        services_to_check.append("power-profiles-daemon")
    if has_tlp:
        services_to_check.append("tlp")
    if has_auto_cpufreq:
        services_to_check.append("auto-cpufreq")
    if package_status["thermald"]["installed"] and cpu["model"] and "intel" in cpu["model"].lower():
        services_to_check.append("thermald")
    service_status = check_services_status(services_to_check) if services_to_check else {}
    power_services = [s for s in ("power-profiles-daemon", "tlp", "auto-cpufreq") if s in service_status]
    active_daemons = [s for s in power_services if service_status[s]["active"]]

    if len(active_daemons) > 1:
        issues.append({
            "severity": "high",
            "title": "Conflicting Power Management Daemons",
            "description": f"Multiple power managers are running: {', '.join(active_daemons)}. This can lead to conflicts, high power consumption, or unstable CPU scaling.",
            "fix": "Disable or remove all but one power manager (e.g., keep auto-cpufreq or power-profiles-daemon, and disable/uninstall tlp)."
        })
    elif len(active_daemons) == 0:
        issues.append({
            "severity": "medium",
            "title": "No Power Management Daemon Active",
            "description": "No power manager service (tlp, auto-cpufreq, or power-profiles-daemon) is active. Your battery life might be suboptimal.",
            "fix": "Install and enable `auto-cpufreq` or `power-profiles-daemon`."
        })

    # 2. SSD Trimming check
    ssd_trim_enabled = check_services_status(["fstrim.timer"])["fstrim.timer"]["enabled"]
    if not ssd_trim_enabled:
        issues.append({
            "severity": "medium",
            "title": "SSD Periodic Trim Disabled",
            "description": "fstrim.timer is not enabled. Periodic SSD trimming helps maintain SSD performance and longevity.",
            "fix_cmd": "sudo systemctl enable --now fstrim.timer",
            "fix": "Enable periodic SSD trimming by running: `sudo systemctl enable --now fstrim.timer`"
        })

    # 3. GPU Driver Check
    intel_gpu = any(gpu["brand"] == "intel" for gpu in gpus)
    nvidia_gpu = any(gpu["brand"] == "nvidia" for gpu in gpus)
    amd_gpu = any(gpu["brand"] == "amd" for gpu in gpus)

    if intel_gpu:
        if not package_status["intel-media-driver"]["installed"] and not package_status["libva-intel-driver"]["installed"]:
            issues.append({
                "severity": "medium",
                "title": "Missing Intel VA-API Hardware Video Decoding Drivers",
                "description": "No Intel hardware acceleration driver (intel-media-driver or libva-intel-driver) was detected. Browsers and video players may use high CPU for video decoding.",
                "fix_cmd": package_command(package_manager, "install", ["intel-media-driver"]),
                "fix": "Install `intel-media-driver` (for Broadwell+) or `libva-intel-driver` (for older Intel GPUs)."
            })
    if amd_gpu:
        if not package_status["libva-mesa-driver"]["installed"]:
            issues.append({
                "severity": "medium",
                "title": "Missing AMD VA-API Drivers",
                "description": "libva-mesa-driver is not installed. AMD graphics need it for hardware video decoding.",
                "fix_cmd": package_command(package_manager, "install", ["libva-mesa-driver"]),
                "fix": "Install `libva-mesa-driver` using the detected package manager."
            })
    if nvidia_gpu:
        if not package_status["nvidia"]["installed"] and not package_status["nvidia-utils"]["installed"]:
            issues.append({
                "severity": "high",
                "title": "Missing NVIDIA Drivers",
                "description": "NVIDIA GPU detected but no proprietary drivers (nvidia, nvidia-utils) were found. Default nouveau drivers have poor 3D performance and power management.",
                "fix_cmd": package_command(package_manager, "install", ["nvidia", "nvidia-utils"]),
                "fix": "Install proprietary drivers using the detected package manager."
            })

    # 4. Intel Thermals
    if cpu["model"] and "intel" in cpu["model"].lower():
        if not package_status["thermald"]["installed"]:
            issues.append({
                "severity": "low",
                "title": "Intel Thermal Daemon Not Installed",
                "description": "thermald prevents Intel CPUs from overheating using active cooling control.",
                "fix_cmd": f"{package_command(package_manager, 'install', ['thermald'])} && sudo systemctl enable --now thermald",
                "fix": "Install and enable `thermald`."
            })
        elif not service_status.get("thermald", {}).get("active"):
            issues.append({
                "severity": "low",
                "title": "Intel Thermal Daemon Installed but Inactive",
                "description": "thermald is installed but the systemd service is not running.",
                "fix_cmd": "sudo systemctl enable --now thermald",
                "fix": "Start and enable the service: `sudo systemctl enable --now thermald`"
            })

    # 5. Failed services
    failed_units, _ = run_cmd("systemctl --failed --quiet")
    if failed_units:
        issues.append({
            "severity": "medium",
            "title": "Failed Systemd Services",
            "description": "One or more systemd services failed to start.",
            "fix": "Run `systemctl --failed` to see the failing units and debug them."
        })

    # 6. Orphaned Packages (pacman exposes a reliable query for this.)
    if package_manager == "pacman":
        orphaned_pkgs, _ = run_cmd(PACKAGE_MANAGER_DEFINITIONS[package_manager]["orphaned"])
        if orphaned_pkgs:
            pkg_list = orphaned_pkgs.replace("\n", ", ")
            issues.append({
                "severity": "low",
                "title": "Orphaned Packages Found",
                "description": f"There are unused dependencies taking up space: {pkg_list}",
                "fix_cmd": "sudo pacman -Rns $(pacman -Qtdq)",
                "fix": "Clean them up by running: `sudo pacman -Rns $(pacman -Qtdq)`"
            })

    # Populate recommendations list (batch availability check, one AUR query total)
    pending_recommendations = []
    for pkg in packages_to_check:
        status = package_status[pkg]
        if package_manager and not status["installed"]:
            # Filter out hardware-incompatible recommendations
            if pkg in ["nvidia", "nvidia-utils"] and not nvidia_gpu:
                continue
            if pkg in ["intel-media-driver", "libva-intel-driver"] and not intel_gpu:
                continue
            if pkg == "libva-mesa-driver" and not amd_gpu:
                continue
            if pkg == "thermald" and (not cpu["model"] or "intel" not in cpu["model"].lower()):
                continue
            if pkg == "tlp" and has_power_daemon:
                continue
            if pkg == "power-profiles-daemon" and has_tlp:
                continue
            if pkg in ["tlp", "power-profiles-daemon", "auto-cpufreq", "powertop"] and not battery["present"]:
                continue
            pending_recommendations.append(pkg)

    availability = check_packages_availability(pending_recommendations, package_manager)
    for pkg in pending_recommendations:
        loc = availability.get(pkg, "not_found")
        if loc == "not_found":
            continue
        recommendations.append({
            "package": pkg,
            "description": package_status[pkg]["description"],
            "source": loc,
            "install_cmd": f"yay -S {pkg}" if loc == "aur" else package_command(package_manager, "install", [pkg])
        })

    return {
        "cpu": cpu,
        "gpus": gpus,
        "battery": battery,
        "memory": get_ram_info(),
        "disks": get_disk_info(),
        "filesystems": get_filesystem_usage(),
        "system": {
            "distribution": os_info["name"],
            "distribution_id": os_info["id"],
            "package_manager": package_manager or "not detected",
        },
        "packages": package_status,
        "issues": issues,
        "cleanup": cleanup_recommendations,
        "recommendations": recommendations
    }
