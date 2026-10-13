import unittest
from pathlib import Path
from queue import Queue
from tempfile import TemporaryDirectory

import numpy as np

from model.dataprocess.frame_by_frame.BuildSideFrame import build_side_frame
from model.utils.StrategyUtil import strategy_name_from_code, validate_strategy_name
from control.DataProcessWorker import DataProcessWorker
from control.LidarAcquisitionStrategies import AcquisitionStrategyFactory, FrameByFrameStrategy
from control.PlcCommunicationProcess import PlcCommunicationProcess
from model.utils.FrameQueueManager import FrameQueueManager
from model.plc.MovingFrameData import ReceiveMovingFrameData


CONFIG_DIR = Path(__file__).resolve().parents[1] / "model" / "tomls"


class FrameOnlyTests(unittest.TestCase):
    def test_frame_strategy_is_accepted(self):
        self.assertEqual(strategy_name_from_code(1), "frame_by_frame")
        self.assertEqual(validate_strategy_name("frame_by_frame"), "frame_by_frame")

    def test_removed_strategies_cannot_be_started(self):
        for value in (2, 3, 0, True, "1"):
            with self.subTest(code=value), self.assertRaises(ValueError):
                strategy_name_from_code(value)
        for name in ("complete_workpiece", "continuous_bidirectional", "unknown"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_strategy_name(name)

    def test_side_frame_preserves_layers_and_extrema(self):
        frame = build_side_frame(
            {"left": [np.array([[3, 10, 0], [7, 12, 0], [9, 20, 0]])]},
            "left",
            {"combined_y_min": 10, "combined_y_max": 40, "y_threshold": 10},
        )
        self.assertEqual(
            [(row.H_Axis, row.V_Axis_Min, row.V_Axis_Max) for row in frame.FrameData],
            [(10, 3, 7), (20, 9, 9), (0, 0, 0)],
        )

    def test_upper_frame_uses_x_layers(self):
        frame = build_side_frame(
            {"left_upper": [np.array([[10, 3, 0], [12, 7, 0], [20, 9, 0]])]},
            "left_upper",
            {"combined_x_min": 10, "combined_x_max": 40, "x_threshold": 10},
        )
        self.assertEqual(
            [(row.H_Axis, row.V_Axis_Min, row.V_Axis_Max) for row in frame.FrameData],
            [(10, 3, 7), (20, 9, 9), (0, 0, 0)],
        )

    def test_acquisition_factory_creates_frame_strategy(self):
        self.assertIsInstance(
            AcquisitionStrategyFactory.create_strategy("frame_by_frame", {}),
            FrameByFrameStrategy,
        )

    def test_debug_data_keeps_empty_z_frame_and_sends_across_fifo_wrap(self):
        packets = Queue()
        with TemporaryDirectory() as directory:
            np.savetxt(Path(directory) / "combined_fixture.txt", [[12, 11, 0], [22, 21, 20]])
            worker = DataProcessWorker(packets, Queue(), Queue(), directory, config_dir=str(CONFIG_DIR))
            worker.directions = ("left", "right", "left_upper", "right_upper")
            worker.accum = {direction: [] for direction in worker.directions}
            worker.translate_data_origin = 1
            worker.read_data_config.update({
                "translate_data_origin": 1, "z_threshold": 10,
                "combined_y_min": 10, "combined_y_max": 40, "y_threshold": 10,
                "combined_x_min": 10, "combined_x_max": 40, "x_threshold": 10,
            })
            worker.max_fifo = 9
            worker._load_all_frames()
            self.assertEqual(worker.max_frame_index, 2)
            for before, after in ((8, 9), (9, 0), (0, 1)):
                self.assertEqual(worker._process_fifo_advance(before, after), 1)
            frames = [packets.get_nowait() for _ in range(3)]
            self.assertEqual([frame["fifo"] for frame in frames], [9, 0, 1])
            self.assertEqual(frames[0]["left"].FrameData[0].V_Axis_Max, 12)
            self.assertEqual(frames[2]["left"].FrameData[1].V_Axis_Max, 22)
            for direction in worker.directions:
                self.assertTrue(all(
                    (row.H_Axis, row.V_Axis_Min, row.V_Axis_Max) == (0, 0, 0)
                    for row in frames[1][direction].FrameData
                ))

    def test_frame_queue_push_and_clear_preserve_fifo(self):
        manager = FrameQueueManager(str(CONFIG_DIR / "SystemConfig.toml"), stack_size=3)
        direction = manager.active_directions[0]
        frame = build_side_frame(
            {direction: [np.array([[10, 1100, 0]])]}, direction,
            {"combined_y_min": 1100, "combined_y_max": 1120, "y_threshold": 10},
        )
        manager.push_frame(direction, frame, repeat_count=2)
        self.assertIs(manager.frame_stack[direction][0], frame)
        self.assertIs(manager.frame_stack[direction][1], frame)
        self.assertEqual(len(manager.frame_stack[direction]), 3)
        manager.clear(direction)
        self.assertTrue(all(
            (row.H_Axis, row.V_Axis_Min, row.V_Axis_Max) == (0, 0, 0)
            for empty_frame in manager.frame_stack[direction] for row in empty_frame.FrameData
        ))

    def test_plc_runtime_does_not_load_machine_or_spray_config(self):
        process = PlcCommunicationProcess.create("frame_by_frame", Queue(), Queue(), Queue())
        process.machine_config_path = str(CONFIG_DIR / "missing_machine_config.toml")
        process.spray_config_path = str(CONFIG_DIR / "missing_spray_config.toml")
        process._initialize_runtime_state()
        for pulse in (0, 10, 20, 30, 40):
            process._update_chain_status(process._pulse_to_chaincountcm(pulse), pulse)
        samples = [process.pulse_queue.get_nowait() for _ in range(5)]
        self.assertEqual(samples[-1]["pulse"], 40)
        self.assertEqual(samples[-1]["status"], "moving_forward")

    def test_plc_response_echoes_heartbeat_and_zeroes_all_other_bytes(self):
        process = PlcCommunicationProcess.create("frame_by_frame", Queue(), Queue(), Queue())
        for heartbeat in (0, 123, -123, 32767):
            with self.subTest(heartbeat=heartbeat):
                incoming = ReceiveMovingFrameData(
                    HeartBeat=heartbeat, ChainPulse=123456, ChainSpeed=77, Status=5, Operate=9,
                )
                incoming.AxisList[0].Pos = 123
                incoming.AxisList[0].Speed = 456
                incoming.AxisList[0].Status = 7
                process.plc_data = incoming
                packet = process._axis_to_moving_frame().to_bytes()
                expected = bytearray(194)
                expected[10:12] = heartbeat.to_bytes(2, "big", signed=True)
                self.assertEqual(packet, bytes(expected))


if __name__ == "__main__":
    unittest.main()
