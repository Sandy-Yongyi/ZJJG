import os
import sys
import time
import math
import queue
import multiprocessing
from model.utils.LoggerUtil import check_and_rotate_log, logger
from model.plc.PlcCommon import PlcManager
from model.utils.TomlLoader import TomlLoader
from model.plc.MovingFrameData import ReceiveMovingFrameData, SendMovingFrameData
from model.utils.StrategyUtil import validate_strategy_name
from model.utils.ProcessHeartbeat import ProcessHeartbeat


class SimulatedPlcData:
    def __init__(self):
        self.ChainPulse = 0
        self.ChainSpeed = 0
        self.ChainStatus = "stopped"
        self.ChainCountCM = 0
        self.Status = 1
        self.Operate = 0
        self.HeartBeat = 0
        self.AxisList = []


class PlcCommunicationProcess(multiprocessing.Process):
    def _text(self, chinese, english):
        return chinese

    def __init__(self, raw_data_queue, pulse_queue, control_queue, machine_data_queue=None, strategy_name="frame_by_frame", heartbeat=None, heartbeat_interval_s: float = 1.0):
        super().__init__()
        self.raw_data_queue = raw_data_queue
        self.pulse_queue = pulse_queue
        self.control_queue = control_queue
        self.machine_data_queue = machine_data_queue
        self.strategy_name = validate_strategy_name(strategy_name)
        self._heartbeat = ProcessHeartbeat(heartbeat, heartbeat_interval_s)
        self.config_dir = os.path.join(os.getcwd(), "model", "tomls")
        self.plc_config_path = os.path.join(self.config_dir, "PlcConfig.toml")
        self.read_data_config_path = os.path.join(self.config_dir, "ReadDataConfig.toml")
        self.plc_config = {}
        self.read_data_config = {}
        self.plc_manager = None
        self.plc_data = None
        self.max_pulse = 160000
        self.max_fifo = 0
        self.pulse_to_mm = 1
        self.fifo_unit_mm = 2
        self.diff_start_pulse = 7
        self.plc_connected = False
        self.plc_reconnect_pending = False
        self.plc_connection_generation = 0
        self.pulse_history = []
        self.chain_motion_status = "stopped"
        self.lidar_status = 0
        self.simulation_mode = False
        self.last_simulation_time = 0
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def _pulse_to_chaincountcm(self, pulse):
        """将 pulse 换算为 chaincountcm。"""
        pulse_to_mm = float(self.pulse_to_mm or 1)
        return int(round(float(pulse) / pulse_to_mm / 10))

    def _resolve_max_fifo(self):
        """基于 pulse 重置阈值推导 chaincountcm 的最大值。"""
        return max(1, self._pulse_to_chaincountcm(self.max_pulse))

    def _get_fifo_step_delta(self, last_fifo: int, current_fifo: int):
        pass  # 采数显示项目不使用此接口

    @staticmethod
    def create(strategy_name, raw_data_queue, pulse_queue, control_queue, machine_data_queue=None, heartbeat=None, heartbeat_interval_s: float = 1.0):
        """保留工厂接口，仅创建按帧采数的 PLC 通信进程。"""
        validate_strategy_name(strategy_name)
        return PlcCommunicationProcess(
            raw_data_queue, pulse_queue, control_queue,
            machine_data_queue=machine_data_queue, strategy_name=strategy_name,
            heartbeat=heartbeat, heartbeat_interval_s=heartbeat_interval_s,
        )

    def run(self):
        logger.info(f"PlcCommunicationProcess.run() entered, pid={os.getpid()}")
        self._heartbeat.touch(force=True)
        # 重定向输出
        if hasattr(self, "stdout"):
            sys.stdout = self.stdout
        if hasattr(self, "stderr"):
            sys.stderr = self.stderr

        try:
            self._initialize_runtime_state()
            # 如果不是模拟模式，初始化PLC连接
            if not self.simulation_mode:
                if not self._initialize_connection():
                    return  # 连接失败退出进程
                # 首次连接后先发送全零帧，再进入接收及心跳回传循环。
                self.plc.send_frame(SendMovingFrameData())
            # time.sleep(5)  # TODO: 调试时使用，正式环境可移除或调整为更短时间，确保PLC连接稳定后再进入主循环
            # 主处理循环
            self._run_main_loop()

        except Exception as e:
            logger.error(f"Critical error in PLC handler: {str(e)}")
            self._heartbeat.sleep(1)
        finally:
            if self.plc_connected:
                self.plc.disconnect(self.connection_type)

    def _initialize_runtime_state(self):
        """只加载 PLC 和采数配置，不加载设备配置或创建规划器。"""
        self.plc_config = TomlLoader.load(self.plc_config_path)
        self.plc_manager = PlcManager(self.plc_config_path)
        self.read_data_config = TomlLoader.load(self.read_data_config_path)
        self.pulse_to_mm = float(self.read_data_config["pulse_to_mm"])
        if not math.isfinite(self.pulse_to_mm) or self.pulse_to_mm <= 0:
            raise ValueError("pulse_to_mm必须为正数")
        self.max_pulse = self.read_data_config.get("max_pulse", 160000)
        self.diff_start_pulse = self.read_data_config.get("diff_start_pulse", 7)
        self.fifo_unit_mm = self.read_data_config.get("fifo_unit_mm", 2)
        self.max_fifo = self._resolve_max_fifo()

    def _initialize_device_runtime_state(self, return_to_safe: bool):
        pass  # 采数显示项目不使用此接口

    def _build_runtime_machine_config(self, cfg: dict):
        pass  # 采数显示项目不使用此接口

    def _create_frame_queue_manager(self):
        pass  # 采数显示项目不使用此接口

    def _initialize_connection(self):
        """初始化PLC连接"""
        try:
            # 获取配置信息
            self.connection_type = self.plc_config["1"]["connection_type"]
            plc_manager = self.plc_manager
            if plc_manager is None:
                raise RuntimeError("PLC manager has not been initialized")
            self.plc = plc_manager.get_plc("1")

            # 初始连接
            if not self.plc.connect(self.connection_type):
                # 初始连接失败后尝试重连
                if not self._handle_connection_error(self.plc):
                    logger.error("PLC initial connection failed permanently. Exiting process.")
                    print(self._text("PLC连接失败，请检查连接并重新运行软件", "PLC connection failed. Check the connection and restart the software."))
                    return False
            print(self._text("PLC连接成功.", "PLC connected."))
            self.plc_connected = True

            return True

        except Exception as e:
            logger.error(f"Connection initialization failed: {str(e)}")
            return False

    def _run_main_loop(self):
        """接收采数脉冲并回传心跳，发送报文的其他字段保持全零。"""
        while True:
            self._heartbeat.sleep(0.09)
            if not self._update_plc_data():
                continue
            self._process_frame_data()
            check_and_rotate_log()
            if not self.simulation_mode:
                try:
                    self.plc.send_frame(self._axis_to_moving_frame())
                except (ConnectionError, OSError) as exc:
                    logger.error(f"PLC heartbeat response failed: {exc}")
                    self._mark_plc_disconnected()
                    if not self._handle_connection_error(self.plc):
                        return

    def _update_plc_data(self):
        try:
            if self.simulation_mode:
                current_time = time.time()
                if self.plc_data is None or current_time - self.last_simulation_time >= 0.3:
                    if not hasattr(self, "simulated_plc_data"):
                        self.simulated_plc_data = ReceiveMovingFrameData(Status=1)
                    pulse_step = max(1, int(round(float(self.fifo_unit_mm) * self.pulse_to_mm)))
                    self.simulated_plc_data.ChainPulse = self._advance_simulated_pulse(
                        self.simulated_plc_data.ChainPulse, pulse_step,
                    )
                    self.plc_data = self.simulated_plc_data
                    self.last_simulation_time = current_time
                else:
                    return False
            else:
                self.plc_data = self.plc.scan(self.connection_type)
            fifo = self._pulse_to_chaincountcm(self.plc_data.ChainPulse)
            setattr(self.plc_data, "ChainCountCM", fifo)
            self.plc_reconnect_pending = False
            self._update_chain_status(fifo, self.plc_data.ChainPulse)
            return True
        except (ConnectionError, OSError) as exc:
            logger.error(f"PLC receive failed: {exc}")
            self._mark_plc_disconnected()
            if not self.simulation_mode and not self._handle_connection_error(self.plc):
                raise
            return False
        except Exception as exc:
            logger.error(f"PLC receive data error: {exc}")
            return False

    def _advance_simulated_pulse(self, current_pulse, pulse_step):
        """仿真脉冲：递增到 max_pulse 时重置为 0。"""
        next_pulse = int(current_pulse) + int(pulse_step)
        reset_threshold = int(self.max_pulse)
        return 0 if next_pulse >= reset_threshold else next_pulse

    def _reset_raw_data_timeout_timer(self, fifo=None):
        pass  # 采数显示项目不使用此接口

    def _update_chain_status(self, fifo, pulse):
        self.pulse_history.append(pulse)
        if len(self.pulse_history) > 5:
            self.pulse_history.pop(0)

        status = "stopped"
        if len(self.pulse_history) == 5:
            pulse_delta = float(self.pulse_history[-1]) - float(self.pulse_history[0])
            half_pulse_range = float(self.max_pulse) / 2.0
            # 脉冲计数由最大值回到0时仍是正向运动，例如159997 -> 4的实际增量为7。
            if pulse_delta < -half_pulse_range:
                pulse_delta += float(self.max_pulse)
            elif pulse_delta > half_pulse_range:
                pulse_delta -= float(self.max_pulse)
            # logger.info(f"pulse_history: {self.pulse_history}")
            # 停止
            if len(set(self.pulse_history)) == 1:
                status = "stopped"
            elif pulse_delta > self.diff_start_pulse:
                status = "moving_forward"
            elif pulse_delta < -self.diff_start_pulse:
                status = "moving_reverse"

        last_status = getattr(self, "chain_motion_status", None)
        self.chain_motion_status = status
        if hasattr(self, "plc_data") and self.plc_data is not None:
            setattr(self.plc_data, "ChainStatus", status)

        if last_status != status:
            if status in ("moving_forward", "moving_reverse") and last_status == "stopped":
                self._reset_raw_data_timeout_timer(fifo=fifo)
        logger.info(f"PLC chain status changed: pulse={pulse}, fifo={fifo}, status={status}")
        self.pulse_queue.put({
            "pulse": pulse,
            "fifo": fifo,
            "status": status,
            "plc_generation": self.plc_connection_generation,
        })

    def _update_lidar_status_from_packet(self, fifo_data: dict):
        pass  # 采数显示项目不使用此接口

    def _should_skip_raw_packet(self):
        pass  # 采数显示项目不使用此接口

    def _process_frame_data(self):
        """消费采集进程的数据与状态，避免队列积压；不执行帧规划。"""
        while True:
            try:
                packet = self.raw_data_queue.get_nowait()
            except queue.Empty:
                break
            if isinstance(packet, dict) and "lidar_status" in packet:
                status = int(packet["lidar_status"] or 0)
                if status != self.lidar_status:
                    logger.info(f"Lidar status changed: {self.lidar_status} -> {status}")
                    self.lidar_status = status

    def _should_drop_reconnect_raw_packet(self, fifo_data: dict):
        pass  # 采数显示项目不使用此接口

    def _process_continuous_scan_cycle(self):
        # 仅保留按帧模式，此接口不再执行。
        pass  # 采数显示项目不使用此接口

    def _publish_continuous_scan_state(self):
        # 仅保留按帧模式，此接口不再执行。
        pass  # 采数显示项目不使用此接口

    def _process_workpiece_data(self):
        # 仅保留按帧模式，此接口不再执行。
        pass  # 采数显示项目不使用此接口

    def _update_workpiece_tracking_after_push(self, direction: str, sn: int, insert_index: int, shifted: bool):
        # 仅保留按帧模式，此接口不再执行。
        pass  # 采数显示项目不使用此接口

    def _build_machine_workpiece(self, block_data, sn: int):
        # 仅保留按帧模式，此接口不再执行。
        pass  # 采数显示项目不使用此接口

    def _handle_frame_packet_received(self, fifo_data: dict, repeat_count: int):
        pass  # 采数显示项目不使用此接口

    def _push_empty_frames(self, repeat_count: int):
        pass  # 采数显示项目不使用此接口

    def _sync_frame_queue_with_chain_fifo(self):
        pass  # 采数显示项目不使用此接口

    def _resync_frame_queue_after_plc_reconnect(self):
        pass  # 采数显示项目不使用此接口

    def _sync_complete_workpiece_positions(self):
        # 仅保留按帧模式，此接口不再执行。
        pass  # 采数显示项目不使用此接口

    def _calc_delta_mm_with_wrap(self, current_mm: float, prev_mm: float):
        # 仅保留按帧模式，此接口不再执行。
        pass  # 采数显示项目不使用此接口

    def _update_raw_data_watchdog(self):
        pass  # 采数显示项目不使用此接口

    def _update_lidar_status(self, new_status: int):
        pass  # 采数显示项目不使用此接口

    def _clear_all_frame_queues(self):
        pass  # 采数显示项目不使用此接口

    def _clear_pending_raw_data_queue(self):
        pass  # 采数显示项目不使用此接口

    def _update_enable_value(self):
        pass  # 采数显示项目不使用此接口

    def _handle_config_update(self, sn: int, config: dict):
        pass  # 采数显示项目不使用此接口

    def _handle_spray_update(self, spray_cfg: dict):
        pass  # 采数显示项目不使用此接口

    def _axis_to_moving_frame(self) -> SendMovingFrameData:
        """兼容旧接口：仅回传收到的心跳，其他发送字段和全部轴数据为零。"""
        response = SendMovingFrameData()
        response.HeartBeat = getattr(self.plc_data, "HeartBeat", 0)
        return response

    def after_spray_complete(self, direction: str, sn: int):
        # 仅保留按帧模式，此接口不再执行。
        pass  # 采数显示项目不使用此接口

    def _handle_connection_error(self, plc):
        """处理连接异常，支持初始连接和已连接状态的断开重连"""
        self.plc_connected = False
        max_retries = self.read_data_config["plc_connect_max_retries"]
        for attempt in range(max_retries):
            try:
                self._heartbeat.touch()
                print(self._text(f"PLC连接失败，正在尝试第{attempt+1}次重连...", f"PLC connection failed; reconnect attempt {attempt+1}..."))
                try:
                    plc.disconnect(connection_type=self.connection_type)
                except Exception:
                    pass
                self._heartbeat.sleep(10)
                # 尝试重连
                if plc.connect(connection_type=self.connection_type):
                    logger.info("PLC reconnected successfully")
                    print(self._text("PLC重连成功.", "PLC reconnected."))
                    self.plc_connected = True
                    return True
            except Exception as e:
                logger.error(f"Reconnect attempt {attempt+1} failed: {str(e)}")

        logger.error(f"Failed to reconnect to PLC after {max_retries} attempts")
        return False

    def _mark_plc_disconnected(self):
        """立即暂停链条相关计时，并通知激光进程 PLC 已断连。"""
        self.plc_connected = False
        self.chain_motion_status = "stopped"
        self.raw_data_timeout_active = False
        self.pulse_history.clear()
        if not self.plc_reconnect_pending:
            self.plc_connection_generation += 1
        self.plc_reconnect_pending = True

        plc_data = getattr(self, "plc_data", None)
        if plc_data is not None:
            setattr(plc_data, "ChainStatus", "stopped")
        fifo = int(getattr(plc_data, "ChainCountCM", 0) or 0)
        self.pulse_queue.put({
            "pulse": -999,
            "fifo": fifo,
            "status": "stopped",
            "plc_generation": self.plc_connection_generation,
        })
        logger.warning(f"PLC disconnected, lidar acquisition paused at fifo={fifo}")
