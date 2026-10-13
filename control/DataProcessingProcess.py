import multiprocessing


class DataProcessingProcess(multiprocessing.Process):
    def __init__(self, raw_data_queue, machine_data_queue, viz_queue=None, config_dir=None,
                 heartbeat=None, heartbeat_interval_s: float = 1.0):
        # 仅保留按帧模式，此接口不再执行。
        super().__init__()
        pass

    def run(self):
        # 仅保留按帧模式，此接口不再执行。
        pass

    def _process_data(self, raw_data):
        # 仅保留按帧模式，此接口不再执行。
        pass

    @staticmethod
    def _has_valid_points(data):
        # 仅保留按帧模式，此接口不再执行。
        pass

    def _build_block_data(self, data, lidar_status, data_dir, same_origin=False):
        # 仅保留按帧模式，此接口不再执行。
        pass

    def _push_visualization_data(self, points, block_data):
        # 仅保留按帧模式，此接口不再执行。
        pass
