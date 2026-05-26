import os
import json
import serial
import serial.tools.list_ports
from time import time, sleep
import gradio as gr
import pygetwindow as gw
import pyautogui

from dbd.AI_model import AI_model
from dbd.utils.directkeys import PressKey, ReleaseKey, SPACE
from dbd.utils.monitoring_mss import Monitoring_mss

try:
    from dbd.utils.monitoring_bettercam import Monitoring_bettercam
    bettercam_ok = True
    print("Info: Bettercam feature available.")
except ImportError:
    bettercam_ok = False

# Config file
CONFIG_FILE = "dbd_config.json"

# RP2350 Hardware Support
rp2350_serial = None
rp2350_connected = False

def get_available_ports():
    """Get list of available COM ports"""
    ports = serial.tools.list_ports.comports()
    port_dict = {}
    
    for port in ports:
        port_dict[port.device] = f"{port.device}"
    
    common_ports = ["COM1", "COM3", "COM4", "COM5", "COM6", "/dev/ttyUSB0", "/dev/ttyUSB1"]
    for port in common_ports:
        if port not in port_dict:
            port_dict[port] = port
    
    return port_dict if port_dict else {"": "No ports found"}

def load_config():
    """Load config from JSON file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return None

def save_config(device, capture_region_size, confidence_threshold, hit_ante, cpu_stress, use_rp2350, rp2350_port, input_delay):
    """Save config to JSON file"""
    config = {
        "device": device,
        "capture_region_size": capture_region_size,
        "confidence_threshold": confidence_threshold,
        "hit_ante": hit_ante,
        "cpu_stress": cpu_stress,
        "use_rp2350": use_rp2350,
        "rp2350_port": rp2350_port,
        "input_delay": input_delay
    }
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return f"✓ Config saved to {CONFIG_FILE}"
    except Exception as e:
        return f"✗ Error saving config: {e}"

def is_game_active():
    """Check if Dead by Daylight window is active"""
    try:
        active_window = gw.getActiveWindow()
        if active_window and ("dead by daylight" in active_window.title.lower() or "dbd" in active_window.title.lower()):
            return True
        return False
    except:
        return False

def focus_game():
    """Try to bring DBD window to focus"""
    try:
        dbd_windows = gw.getWindowsWithTitle("Dead by Daylight")
        if not dbd_windows:
            dbd_windows = gw.getWindowsWithTitle("dbd")
        if dbd_windows:
            dbd_windows[0].activate()
            sleep(0.1)
            return True
    except:
        pass
    return False

def connect_rp2350(port):
    """Connect to RP2350 on specified port"""
    global rp2350_serial, rp2350_connected
    
    if " - " in str(port):
        port = str(port).split(" - ")[0]
    
    port = str(port).strip()
    if not port or port == "":
        print("[RP2350] No port specified")
        return False
    
    try:
        if rp2350_serial:
            try:
                rp2350_serial.close()
            except:
                pass
        rp2350_serial = serial.Serial(port, 115200, timeout=1)
        sleep(0.5)
        rp2350_connected = True
        print(f"[RP2350] ✓ Connected to {port}")
        return True
    except Exception as e:
        rp2350_connected = False
        print(f"[RP2350] ✗ Failed to connect: {e}")
        return False

def disconnect_rp2350():
    """Disconnect from RP2350"""
    global rp2350_serial, rp2350_connected
    try:
        if rp2350_serial:
            rp2350_serial.close()
        rp2350_connected = False
    except:
        pass

def press_space_rp2350(input_delay=0.005):
    """Send spacebar press command to RP2350"""
    global rp2350_serial, rp2350_connected
    
    if not is_game_active():
        focus_game()
        sleep(0.1)
    
    if not rp2350_connected or not rp2350_serial:
        return False
    
    try:
        rp2350_serial.write(b"HIT\n")
        rp2350_serial.flush()
        sleep(input_delay)
        
        if rp2350_serial.in_waiting > 0:
            response = rp2350_serial.read(100)
            if b"ACK" in response:
                return True
        return False
    except Exception as e:
        print(f"[RP2350] Error: {e}")
        rp2350_connected = False
        return False

ai_model = None
def cleanup():
    global ai_model
    disconnect_rp2350()
    if ai_model is not None:
        del ai_model
        ai_model = None
    return 0.


def monitor(ai_model_path, device, monitoring_str, monitor_id, hit_ante, nb_cpu_threads, use_rp2350, rp2350_port, confidence_threshold, capture_region_size, input_delay):
    if ai_model_path is None or not os.path.exists(ai_model_path):
        raise gr.Error("Invalid AI model file", duration=0)

    if device is None:
        raise gr.Error("Invalid device option")

    if isinstance(monitor_id, (list, tuple)):
        monitor_id = monitor_id[1] if len(monitor_id) > 1 else monitor_id[0]

    if monitor_id is None or monitor_id == "":
        raise gr.Error("Invalid monitor option")

    use_gpu = (device == devices[1])

    if not is_game_active():
        gr.Warning("⚠️ DBD not focused! Please click on the game window.")

    if use_rp2350 and rp2350_port:
        if not connect_rp2350(rp2350_port):
            gr.Warning("Could not connect to RP2350. Using software keyboard.")
            use_rp2350 = False

    if monitoring_str == "bettercam" and bettercam_ok:
        monitoring = Monitoring_bettercam(monitor_id=monitor_id, crop_size=224, target_fps=240)
    else:
        monitoring = Monitoring_mss(monitor_id=monitor_id, crop_size=224, capture_size=capture_region_size)

    try:
        global ai_model
        ai_model = AI_model(ai_model_path, use_gpu, nb_cpu_threads, monitoring)
        execution_provider = ai_model.check_provider()
    except Exception as e:
        raise gr.Error("Error when loading AI model: {}".format(e), duration=0)

    if execution_provider == "CUDAExecutionProvider":
        gr.Info("✓ GPU: NVIDIA CUDA")
    elif execution_provider == "DmlExecutionProvider":
        gr.Info("✓ GPU: AMD DirectML")
    elif execution_provider == "TensorRT":
        gr.Info("✓ GPU: TensorRT (NVIDIA)")
    else:
        gr.Info(f"✓ CPU: {nb_cpu_threads} threads")

    input_method = "RP2350" if (use_rp2350 and rp2350_connected) else "Software Keyboard"
    gr.Info(f"Input: {input_method} | Delay: {input_delay}ms | Game Focus: {'✓' if is_game_active() else '✗'}")

    t0 = time()
    nb_frames = 0
    hits = 0

    try:
        while True:
            if use_rp2350 and nb_frames % 60 == 0:
                if not is_game_active():
                    focus_game()

            frame_np = ai_model.grab_screenshot()
            nb_frames += 1

            pred, desc, probs, should_hit = ai_model.predict(frame_np)
            max_confidence = max(probs.values())

            if should_hit and max_confidence >= confidence_threshold:
                if pred == 2 and hit_ante > 0:
                    sleep(hit_ante * 0.001)

                if use_rp2350:
                    if is_game_active() or focus_game():
                        press_space_rp2350(input_delay / 1000.0)
                    else:
                        print("[WARNING] Could not focus game")
                else:
                    PressKey(SPACE)
                    sleep(0.005)
                    ReleaseKey(SPACE)

                hits += 1
                yield gr.skip(), frame_np, probs
                sleep(0.5)
                t0 = time()
                nb_frames = 0
                continue

            t_diff = time() - t0
            if t_diff > 1.0:
                fps = round(nb_frames / t_diff, 1)
                yield fps, gr.skip(), gr.skip()
                t0 = time()
                nb_frames = 0

    except Exception as e:
        print(f"Monitoring error: {e}")
    finally:
        print(f"Monitoring stopped. Total hits: {hits}")
        disconnect_rp2350()


if __name__ == "__main__":
    models_folder = "models"

    fps_info = "AI inference speed"
    devices = ["CPU", "GPU"]
    cpu_choices = [("Low (2)", 2), ("Normal (4)", 4), ("High (6)", 6), ("Max (8)", 8)]
    capture_choices = [("Small (224)", 224), ("Medium (320)", 320), ("Large (416)", 416)]
    delay_choices = [("1ms", 1), ("5ms", 5), ("10ms", 10), ("15ms", 15), ("20ms", 20), ("30ms", 30), ("45ms", 45)]

    model_files = [(f, f'{models_folder}/{f}') for f in os.listdir(f"{models_folder}/") if f.endswith(".onnx") or f.endswith(".trt")]
    if len(model_files) == 0:
        raise gr.Error(f"No AI model found in {models_folder}/", duration=0)

    monitoring_choices = ["mss", "bettercam"] if bettercam_ok else ["mss"]
    def switch_monitoring_cb(monitoring_str):
        if monitoring_str == "bettercam" and bettercam_ok:
            monitor_choices = Monitoring_bettercam.get_monitors_info()
        else:
            monitor_choices = Monitoring_mss.get_monitors_info()
        return gr.update(choices=monitor_choices, value=None), None

    monitor_choices = Monitoring_mss.get_monitors_info()

    rp2350_ports = get_available_ports()
    default_port = list(rp2350_ports.keys())[0] if rp2350_ports else ""

    # Load config
    saved_config = load_config()
    default_device = saved_config.get("device", devices[1]) if saved_config else devices[1]
    default_capture = saved_config.get("capture_region_size", 320) if saved_config else 320
    default_confidence = saved_config.get("confidence_threshold", 0.30) if saved_config else 0.30
    default_hit_ante = saved_config.get("hit_ante", 20) if saved_config else 20
    default_cpu_stress = saved_config.get("cpu_stress", 4) if saved_config else 4
    default_use_rp2350 = saved_config.get("use_rp2350", True) if saved_config else True
    default_rp2350_port = saved_config.get("rp2350_port", default_port) if saved_config else default_port
    default_input_delay = saved_config.get("input_delay", 5) if saved_config else 5

    with (gr.Blocks(title="DBD Auto Skill Check - RP2350") as webui):
        gr.Markdown("<h1 style='text-align: center;'>⚡ DBD Auto Skill Check</h1>")
        gr.Markdown("<p style='text-align: center;'>Powered by RP2350 Hardware | 100% Accuracy</p>")

        with gr.Row():
            with gr.Column(variant="panel"):
                with gr.Column(variant="panel"):
                    gr.Markdown("### 🤖 AI Model")
                    ai_model_path = gr.Dropdown(choices=model_files, value=model_files[0][1], label="AI Model")
                    device = gr.Radio(choices=devices, value=default_device, label="Device")
                    with gr.Row():
                        monitoring_str = gr.Dropdown(choices=monitoring_choices, value=monitoring_choices[0], label="Capture Method")
                        monitor_id = gr.Dropdown(choices=monitor_choices, value=monitor_choices[0][1], label="Monitor")
                
                with gr.Column(variant="panel"):
                    gr.Markdown("### ⚙️ Settings")
                    capture_region_size = gr.Radio(
                        label="Capture Size",
                        choices=capture_choices,
                        value=default_capture,
                    )
                    confidence_threshold = gr.Slider(
                        minimum=0.1, maximum=1.0, step=0.05, value=default_confidence,
                        label="Confidence Threshold",
                    )
                    hit_ante = gr.Slider(minimum=0, maximum=225, step=1, value=default_hit_ante, label="Hit Delay (ms)")
                    cpu_stress = gr.Radio(label="CPU Threads", choices=cpu_choices, value=default_cpu_stress)
                
                with gr.Column(variant="panel"):
                    gr.Markdown("### 🎮 RP2350 Hardware")
                    use_rp2350 = gr.Checkbox(value=default_use_rp2350, label="✓ Enable RP2350")
                    rp2350_port = gr.Dropdown(choices=rp2350_ports, value=default_rp2350_port, label="COM Port", allow_custom_value=True)
                    input_delay = gr.Radio(label="Input Delay", choices=delay_choices, value=default_input_delay)
                
                with gr.Column():
                    run_button = gr.Button("▶ START", variant="primary", size="lg")
                    stop_button = gr.Button("⏹ STOP", variant="stop", size="lg")
                
                with gr.Column(variant="panel"):
                    gr.Markdown("### 💾 Config")
                    save_config_button = gr.Button("💾 Save Config", variant="secondary")
                    config_status = gr.Textbox(label="Status", interactive=False, value="Config loaded" if saved_config else "No config file")

            with gr.Column(variant="panel"):
                fps = gr.Number(label="FPS", interactive=False)
                image_visu = gr.Image(label="Last Skill Check", height=224, interactive=False)
                probs = gr.Label(label="Detection")

        # Save config button action
        save_config_button.click(
            fn=lambda d, cs, ct, ha, cpu, ur, rp, id: save_config(d, cs, ct, ha, cpu, ur, rp, id),
            inputs=[device, capture_region_size, confidence_threshold, hit_ante, cpu_stress, use_rp2350, rp2350_port, input_delay],
            outputs=[config_status]
        )

        monitoring = run_button.click(
            fn=monitor, 
            inputs=[ai_model_path, device, monitoring_str, monitor_id, hit_ante, cpu_stress, use_rp2350, rp2350_port, confidence_threshold, capture_region_size, input_delay],
            outputs=[fps, image_visu, probs]
        )

        stop_button.click(fn=cleanup, inputs=None, outputs=fps)
        monitoring_str.blur(fn=switch_monitoring_cb, inputs=[monitoring_str], outputs=[monitor_id, image_visu])

    try:
        webui.launch()
    except:
        print("Stopped by user")
    finally:
        cleanup()