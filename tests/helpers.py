from pathlib import Path


def mangohud(path: Path, frames: list[float], *, interval_ms=None, versioned=False, system="Linux,CPU,GPU,32G,kernel,driver,performance"):
    prefix = "v1\n0.8.4\n----------------SYSTEM INFO----------------\n" if versioned else ""
    rows = [prefix + "os,cpu,gpu,ram,kernel,driver,cpuscheduler", system]
    if versioned:
        rows.append("----------------FRAME METRICS----------------")
    rows.append("fps,frametime,cpu_load,cpu_power,gpu_load,cpu_temp,gpu_temp,gpu_core_clock,gpu_mem_clock,gpu_vram_used,gpu_power,ram_used,swap_used,process_rss,cpu_mhz,elapsed")
    elapsed = 0
    for i, ft in enumerate(frames):
        elapsed += ft if interval_ms is None else interval_ms
        rows.append(f"{1000/ft},{ft},40,55,85,60,57,2100,1800,5,180,10,0,0,4400,{elapsed*1e6:.0f}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n")
    return path
