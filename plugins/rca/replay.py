from datetime import datetime, timedelta
import re
from os import listdir
from os.path import isfile, join
import argparse

log_type_dict = {
    1: 'TRANS_SERVICE_LOG_BASE_TYPE',
    2: 'TABLET_OP_LOG_BASE_TYPE',
    3: 'STORAGE_SCHEMA_LOG_BASE_TYPE',
    4: 'TABLET_SEQ_SYNC_LOG_BASE_TYPE',
    5: 'DDL_LOG_BASE_TYPE',
    6: 'KEEP_ALIVE_LOG_BASE_TYPE',
    7: 'TIMESTAMP_LOG_BASE_TYPE',
    8: 'TRANS_ID_LOG_BASE_TYPE',
    9: 'GC_LS_LOG_BASE_TYPE',
    10: 'MAJOR_FREEZE_LOG_BASE_TYPE',
    11: 'PRIMARY_LS_SERVICE_LOG_BASE_TYPE',
    12: 'RECOVERY_LS_SERVICE_LOG_BASE_TYPE',
    13: 'STANDBY_TIMESTAMP_LOG_BASE_TYPE',
    14: 'GAIS_LOG_BASE_TYPE',
    15: 'DAS_ID_LOG_BASE_TYPE',
    16: 'RESTORE_SERVICE_LOG_BASE_TYPE',
    17: 'RESERVED_SNAPSHOT_LOG_BASE_TYPE',
    18: 'MEDIUM_COMPACTION_LOG_BASE_TYPE',
    19: 'ARB_GARBAGE_COLLECT_SERVICE_LOG_BASE_TYPE',
    20: 'DATA_DICT_LOG_BASE_TYPE',
    21: 'ARBITRATION_SERVICE_LOG_BASE_TYPE',
    22: 'NET_STANDBY_TNT_SERVICE_LOG_BASE_TYPE',
    23: 'NET_ENDPOINT_INGRESS_LOG_BASE_TYPE',
    24: 'HEARTBEAT_SERVICE_LOG_BASE_TYPE',
    25: 'PADDING_LOG_BASE_TYPE',
    26: 'DUP_TABLE_LOG_BASE_TYPE',
    27: 'OBJ_LOCK_GARBAGE_COLLECT_SERVICE_LOG_BASE_TYPE',
}

s = 'observer.log.20230225144757584:[2023-02-25 14:47:49.740726] ERROR try_recycle_blocks (palf_env_impl.cpp:688) [68708][T1014_PalfGC][T1014][Y0-0000000000000000-0-0] [lt=2][errcode=-4264] Log out of disk space(msg="log disk space is almost full", ret=-4264, total_size(MB)=22118, used_size(MB)=20470, used_percent(%)=92, warn_size(MB)=17694, warn_percent(%)=80, limit_size(MB)=21012, limit_percent(%)=95, maximum_used_size(MB)=20132, maximum_log_stream=1001, oldest_log_stream=1001, oldest_scn={val:1677248265845607707})'


class CommonUtil:
    @staticmethod
    def parse_tenant_id(line):
        p = "\[T(?P<tenant_id>\d+)\]"
        m = re.search(p, line)
        tenant_id = 0
        if m:
            tenant_id = int(m.group('tenant_id'))
        return tenant_id

    @staticmethod
    def is_tenant_log(tenant_id, line):
        t_tenant_id = CommonUtil.parse_tenant_id(line)
        return tenant_id == t_tenant_id

    @staticmethod
    def parse_log_time(line):
        p = "\[(?P<date_time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\]"
        m = re.search(p, line)
        return datetime.strptime(m.group('date_time'), "%Y-%m-%d %H:%M:%S.%f")

    @staticmethod
    def str_to_time(line):
        p = "(?P<date_time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)"
        m = re.search(p, line)
        return datetime.strptime(m.group('date_time'), "%Y-%m-%d %H:%M:%S.%f")

    @staticmethod
    def parse_ls_id(line):
        # ls_id={id:1001}
        # ls_id_={id:1}
        # ls_id_:{id:1001}
        ls_id = 0
        p = "ls_id=\{id:(?P<ls_id>\d+)\}"
        m = re.search(p, line)
        p = "ls_id_=\{id:(?P<ls_id>\d+)\}"
        if not m:
            m = re.search(p, line)
        p = "ls_id_:\{id:(?P<ls_id>\d+)\}"
        if not m:
            m = re.search(p, line)
        if m:
            ls_id = int(m.group('ls_id'))
        return ls_id

    @staticmethod
    def is_ls_log(ls_id, line):
        t_ls_id = CommonUtil.parse_ls_id(line)
        return ls_id == t_ls_id

    @staticmethod
    def parse_kv_s_i(line):
        d = dict()
        # oldest_log_stream=1001
        p = "(?P<key>[\w|_]+)=(?P<value>\d+)"
        m = re.finditer(p, line)
        for i in m:
            d[i.group('key')] = int(i.group('value'))
        return d

    @staticmethod
    def parse_dict_kv_s_i(line):
        d = dict()
        # oldest_log_stream=1001
        p = "(?P<key>[\w|_]+):(?P<value>\d+)"
        m = re.finditer(p, line)
        for i in m:
            d[i.group('key')] = int(i.group('value'))
        return d

    @staticmethod
    def parse_kv_s_s(line):
        d = dict()
        # service_type="TRANS_SERVICE"
        p = '(?P<key>[\w|_]+)=\"(?P<value>\w+)\"'
        m = re.finditer(p, line)
        for i in m:
            d[i.group('key')] = i.group('value')
        return d

    @staticmethod
    def timestamp_to_datetime(timestamp):
        return datetime.fromtimestamp(float(timestamp) / 1000000)


class LOGFileCommonUtil:
    @staticmethod
    def gen_log_file_name(log_time):
        return "observer.log." + log_time.strftime("%Y%m%d%H%M%S%f")

    @staticmethod
    def get_log_file_list(mypath):
        onlyfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]
        res = [i for i in onlyfiles if i.startswith('observer.log')]
        return res

    @staticmethod
    def get_first_log_time(filename):
        f = open(filename, 'r')
        logtime = None
        for line in f:
            try:
                logtime = CommonUtil.parse_log_time(line)
            except Exception as e:
                pass
            else:
                break
        return logtime

    @staticmethod
    def get_log_file_between(filedir, start_time, end_time, files):
        start_f_name = LOGFileCommonUtil.gen_log_file_name(start_time)
        end_f_name = LOGFileCommonUtil.gen_log_file_name(end_time)
        res = [f for f in files if f >= start_f_name and f <= end_f_name]
        special_file = "observer.log"
        log_time = LOGFileCommonUtil.get_first_log_time(join(filedir, special_file))
        if log_time >= start_time and log_time <= end_time:
            res.append(special_file)
        return res


class CLOGCommonUtil:
    @staticmethod
    def scn_to_datetime(scn):
        return datetime.fromtimestamp(float(scn) / 1000000000)


s_replay = '[2023-02-28 15:41:41.615214] INFO  [CLOG] get_min_unreplayed_log_info (ob_replay_status.cpp:1025) [183155][T1020_TenantWea][T1020][Y0-0000000000000000-0-0] [lt=22] get_min_unreplayed_log_info(lsn={lsn:537327734}, scn={val:1677522022928086323}, this={ls_id_:{id:1001}, is_enabled_:true, is_submit_blocked_:false, role_:1, err_info_:{lsn_:{lsn:18446744073709551615}, scn_:{val:0}, log_type_:0, is_submit_err_:false, err_ts_:0, err_ret_:0}, ref_cnt_:2, post_barrier_lsn_:{lsn:18446744073709551615}, pending_task_count_:0, submit_log_task_:{ObReplayServiceSubmitTask:{type_:1, enqueue_ts_:1677570101608334, err_info_:{has_fatal_error_:false, fail_ts_:0, fail_cost_:1655842, ret_code_:0}}, next_to_submit_lsn_:{lsn:537327734}, committed_end_lsn_:{lsn:537327734}, next_to_submit_scn_:{val:1677522022928086323}, base_lsn_:{lsn:268419072}, base_scn_:{val:1677505291781075774}, iterator_:{iterator_impl:{buf_:0x7f4946405000, next_round_pread_size:2117632, curr_read_pos:122, curr_read_buf_start_pos:0, curr_read_buf_end_pos:122, log_storage_:{IteratorStorage:{start_lsn:{lsn:537327612}, end_lsn:{lsn:537327734}, read_buf:{buf_len_:2121728, buf_:0x7f4946405000}, block_size:67104768, log_storage_:0x7f602b8c5070, read_buf_has_log_block_header:false}, IteratorStorageType::"DiskIteratorStorage"}, curr_entry_is_raw_write:false, curr_entry_size:0, prev_entry_scn:{val:1677522022928086322}, curr_entry:{LogEntryHeader:{magic:19528, version:1, log_size:34, scn_:{val:1677522022928086322}, data_checksum:154833137, flag:0}}, init_mode_version:0}}}})'


class CLOGReplayPointLog:
    @staticmethod
    def is_replay_point_log(line):
        p = "get_min_unreplayed_log_info"
        res = re.search(p, line)
        return res >= 0

    @staticmethod
    def parse_replay_scn(line):
        p = "scn=\{val:(?P<scn>\d+)\},"
        p1 = "scn=\{val:(?P<scn>\d+),"
        m = re.search(p, line)
        if not m:
            m = re.search(p1, line)
        if not m:
            print("parse_replay_scn failed", line)
        return int(m.group('scn'))

    @staticmethod
    def is_follower_log(line):
        d = CommonUtil.parse_dict_kv_s_i(line)
        return 2 == d['role_']

    @staticmethod
    def is_replay_stuck(line):
        # the replay should not stuck for 30 second
        stuck_delta = timedelta(minutes=0.5)
        log_time = CommonUtil.parse_log_time(line)
        replay_scn = CLOGReplayPointLog.parse_replay_scn(line)
        scn_time = CLOGCommonUtil.scn_to_datetime(replay_scn)

        return log_time - scn_time > stuck_delta


s_replay_submit = '[2023-03-15 02:54:18.924545] INFO  [CLOG] check_can_submit_log_replay_task_ (ob_log_replay_service.cpp:919) [3101][T1002_ReplaySrv][T1002][Y0-0000000000000000-0-0] [lt=43] submit replay task need retry(ret=-4023, replay_status={ls_id_:{id:1002}, is_enabled_:true, is_submit_blocked_:false, role_:2, err_info_:{lsn_:{lsn:18446744073709551615}, scn_:{val:0}, log_type_:0, is_submit_err_:false, err_ts_:0, err_ret_:0}, ref_cnt_:2, post_barrier_lsn_:{lsn:18446744073709551615}, pending_task_count_:0, submit_log_task_:{ObReplayServiceSubmitTask:{type_:1, enqueue_ts_:1678820058924418, err_info_:{has_fatal_error_:false, fail_ts_:1678820057918638, fail_cost_:1684661279, ret_code_:-4023}}, next_to_submit_lsn_:{lsn:249675719192}, committed_end_lsn_:{lsn:318345664041}, next_to_submit_scn_:{val:1678818773053498492}, base_lsn_:{lsn:0}, base_scn_:{val:1678801659077434360}, iterator_:{iterator_impl:{buf_:0x7f709aa05000, next_round_pread_size:2121728, curr_read_pos:1799087, curr_read_buf_start_pos:0, curr_read_buf_end_pos:2121728, log_storage_:{IteratorStorage:{start_lsn:{lsn:249673920161}, end_lsn:{lsn:249676041889}, read_buf:{buf_len_:2125824, buf_:0x7f709aa05000}, block_size:67104768, log_storage_:0x7f703a3f8070}, IteratorStorageType::"DiskIteratorStorage"}, curr_entry_is_raw_write:false, curr_entry_size:260041, prev_entry_scn:{val:1678818773053498492}, curr_entry:{LogEntryHeader:{magic:19528, version:1, log_size:260009, scn_:{val:1678818773053498492}, data_checksum:1248814280, flag:1}}, init_mode_version:0, accumlate_checksum:1264936096}}}}, replay_task={ls_id_:{id:1002}, log_type_:1, lsn_:{lsn:249675719248}, scn_:{val:1678818773053498492}, is_pre_barrier_:false, is_post_barrier_:false, log_size_:260009, replay_hint_:3353829, is_raw_write_:false, first_handle_ts_:-1, replay_cost_:-1, retry_cost_:-1, log_buf_:0x7f6da2702308}, is_wait_barrier=false, is_tenant_out_of_mem=true)'


class ReplaySubmitLog:
    @staticmethod
    def is_replay_submit_log(line):
        p = "submit replay task need retry"
        res = re.search(p, line)
        return res >= 0

    @staticmethod
    def is_tenant_out_of_mem(line):
        p = "is_tenant_out_of_mem=true"
        res = re.search(p, line)
        return res >= 0


class ReplaySlowLog:
    log_type_pattern1 = None
    log_type_pattern2 = None

    @staticmethod
    def is_replay_slow_log(line):
        p = "single replay task cost too much time"
        res = re.search(p, line)
        return res >= 0

    @staticmethod
    def get_log_type(line):
        log_type = None
        if ReplaySlowLog.log_type_pattern1 is None:
            p = "log_type_:(?P<log_type>\d+)"
            ReplaySlowLog.log_type_pattern1 = re.compile(p)
        if ReplaySlowLog.log_type_pattern2 is None:
            p = "log_type:(?P<log_type>\d+)"
            ReplaySlowLog.log_type_pattern2 = re.compile(p)
        m = ReplaySlowLog.log_type_pattern1.finditer(line)
        for i in m:
            log_type = i.group('log_type')
        if log_type is None:
            m = ReplaySlowLog.log_type_pattern2.finditer(line)
            for i in m:
                log_type = i.group('log_type')
        return int(log_type)

    @staticmethod
    def get_replay_cost(line):
        replay_cost = line.split('replay_cost_:')[1].split(',')[0]
        return int(replay_cost)


class SlowReplayChecker:
    PREFIX = '[REPLAY DETECT] '
    ENDL = '\n'
    NEXT_SEC = '\n\n'

    def __init__(self, tenant_id, ls_id, start_check_time, interval=60, log_dir_path='./', res_file='result.txt'):
        self.res_file = res_file
        self.log_dir_path = log_dir_path
        self.interval = interval
        self.step = 1
        self.tenant_id = tenant_id
        self.ls_id = ls_id
        self.rfd = None  # the result file fd
        self.log_time = start_check_time  # the time of the error log
        self.need_check_log_files = None  # the log file that need to be examed

    def __prepare(self):
        # open the result file
        self.rfd = open('result.txt', 'w')

        self.rfd.write(self.PREFIX + str(self.step) + ' ANALYZE REPLAY:' + self.ENDL)
        self.rfd.write('tenant_id:{tenant_id}, ls_id:{ls_id}, log_time:{log_time}'.format(tenant_id=self.tenant_id, ls_id=self.ls_id, log_time=self.log_time) + self.ENDL)
        self.rfd.write(self.NEXT_SEC)
        self.step = self.step + 1

    def __get_log_files(self):
        start_log_time = self.log_time - timedelta(minutes=self.interval)
        all_log_files = LOGFileCommonUtil.get_log_file_list(self.log_dir_path)
        self.need_check_log_files = LOGFileCommonUtil.get_log_file_between(self.log_dir_path, start_log_time, self.log_time, all_log_files)
        # pop observer.log and move it to last file.
        self.need_check_log_files.sort()
        special_file = "observer.log"
        if self.need_check_log_files.count(special_file) != 0:
            index = self.need_check_log_files.index(special_file)
            self.need_check_log_files.pop(index)
            self.need_check_log_files.append(special_file)
        self.need_check_log_files.reverse()

    def __next_log_file(self, fname=''):
        rfname = ''
        if not fname:
            pass
        else:
            try:
                index = self.need_check_log_files.index(fname)
                if index == (len(self.need_check_log_files) - 1):
                    rfname = ''
                else:
                    rfname = self.need_check_log_files[index + 1]
            except Exception as e:
                print("find the nex file of {fname} failed, the file index is {index}, the log file array is {array}".format(fname=fname, index=index, array=self.need_check_log_files))
        return rfname

    def __check_exist_log(self, check_func, fname):
        exist_log = False
        if fname:
            f = open(join(self.log_dir_path, fname), 'r')
            for line in f:
                if not CommonUtil.is_tenant_log(self.tenant_id, line):
                    continue
                elif not CommonUtil.is_ls_log(self.ls_id, line):
                    continue
                elif not check_func(line):
                    continue
                else:
                    exist_log = True
            f.close()
        return exist_log

    def __check_replay_stuck(self, fname):
        self.rfd.write(self.PREFIX + str(self.step) + ' DETECT WHETHER REPLAY STUCK:' + self.ENDL)
        while not self.__check_exist_log(CLOGReplayPointLog.is_replay_point_log, fname):
            fname = self.__next_log_file(fname)
            if not fname:
                break

        exist_log = False
        is_follower = False
        is_replay_stuck = False
        replay_scn = 0
        replay_scn_time = 0

        if fname:
            f = open(join(self.log_dir_path, fname), 'r')
            for line in f:
                if not CommonUtil.is_tenant_log(self.tenant_id, line):
                    continue
                elif not CommonUtil.is_ls_log(self.ls_id, line):
                    continue
                elif not CLOGReplayPointLog.is_replay_point_log(line):
                    continue
                else:
                    exist_log = True
                    if not CLOGReplayPointLog.is_follower_log(line):
                        continue
                    else:
                        is_follower = True
                        replay_scn = CLOGReplayPointLog.parse_replay_scn(line)
                        replay_scn_time = CLOGCommonUtil.scn_to_datetime(replay_scn)
                        log_time = CommonUtil.parse_log_time(line)
                        is_replay_stuck = CLOGReplayPointLog.is_replay_stuck(line)
                        break
            f.close()
        if not exist_log:
            self.rfd.write('THERE IS NO REPLAY POINT LOG AT FILE: {fname}'.format(fname=fname) + self.ENDL)
        elif not is_follower:
            self.rfd.write('THE LS IS LEADER: {ls_id}'.format(ls_id=self.ls_id) + self.ENDL)
        else:
            if is_replay_stuck:
                self.rfd.write('REPLAY IS STUCK' + self.ENDL)
                self.rfd.write('LOG_TIME:{log_time}, REPLAY_SCN_TIME:{replay_scn_time}, GAP:{gap}'.format(log_time=str(log_time), replay_scn_time=str(replay_scn_time), gap=str(log_time - replay_scn_time)) + self.ENDL)
                self.rfd.write('REPLAY POINT: {replay_scn}'.format(replay_scn=replay_scn) + self.ENDL)
            else:
                self.rfd.write('REPLAY NOT STUCK' + self.ENDL)
            self.rfd.write(line + self.ENDL)
        self.rfd.write(self.NEXT_SEC)
        self.step = self.step + 1

        return fname, is_replay_stuck

    def __check_memstore_full(self, fname):
        self.rfd.write(self.PREFIX + str(self.step) + ' DETECT WHETHER MEMSTORE FULL:' + self.ENDL)
        while not self.__check_exist_log(ReplaySubmitLog.is_replay_submit_log, fname):
            fname = self.__next_log_file(fname)
            if not fname:
                break

        is_memstore_full = False
        line = ''
        if fname:
            f = open(join(self.log_dir_path, fname), 'r')
            for line in f:
                if not CommonUtil.is_tenant_log(self.tenant_id, line):
                    continue
                elif not CommonUtil.is_ls_log(self.ls_id, line):
                    continue
                elif not ReplaySubmitLog.is_replay_submit_log(line):
                    continue
                elif ReplaySubmitLog.is_tenant_out_of_mem(line):
                    is_memstore_full = True
                    break
            f.close()
        if is_memstore_full:
            self.rfd.write('MEMSTORE IS FULL' + self.ENDL)
            self.rfd.write(line + self.ENDL)
        else:
            self.rfd.write('MEMSTORE IS NORMAL' + self.ENDL)

        self.rfd.write(self.NEXT_SEC)
        self.step = self.step + 1

        return fname

    def __check_slow_replay(self, fname):
        self.rfd.write(self.PREFIX + str(self.step) + ' DETECT SLOW REPLAY:' + self.ENDL)
        while not self.__check_exist_log(ReplaySlowLog.is_replay_slow_log, fname):
            fname = self.__next_log_file(fname)
            if not fname:
                break

        slow_replay_lines = []
        slow_replay_count_dict = {}
        count = 0
        if fname:
            f = open(join(self.log_dir_path, fname), 'r')
            for line in f:
                if not CommonUtil.is_tenant_log(self.tenant_id, line):
                    continue
                elif not CommonUtil.is_ls_log(self.ls_id, line):
                    continue
                elif not ReplaySlowLog.is_replay_slow_log(line):
                    continue
                else:
                    slow_replay_lines.append(line)
                    count += 1
                    log_type = ReplaySlowLog.get_log_type(line)
                    if log_type not in slow_replay_count_dict:
                        slow_replay_count_dict[log_type] = 1
                    else:
                        slow_replay_count_dict[log_type] += 1
            f.close()
            if count != 0:
                self.rfd.write('SLOW REPLAY LIST:' + self.ENDL)
                for k, v in slow_replay_count_dict.items():
                    self.rfd.write('log_type:' + str(k) + ',' + log_type_dict.get(k, "unkown type") + ', slow_replay_count:' + str(v) + self.ENDL)
                self.rfd.write(self.ENDL)
                for line in slow_replay_lines:
                    self.rfd.write(line)
            else:
                self.rfd.write('NO SLOW REPLAY' + self.ENDL)

        self.rfd.write(self.NEXT_SEC)
        self.step = self.step + 1
        return fname

    def __finish(self):
        self.rfd.close()

    def execute(self):
        # 1. prepare the replay check
        self.__prepare()
        # 2. get log file
        self.__get_log_files()

        # begin check a log file
        last_fname = ''
        if self.need_check_log_files:
            last_fname = self.need_check_log_files[0]
        if last_fname:
            # 3. check replay stuck?
            last_fname, _ = self.__check_replay_stuck(last_fname)

            # 4. detect memstore full?
            # memstore full may be because too many replay task pending.
            last_fname = self.__check_memstore_full(last_fname)
            # 5. detect slow replay
            last_fname = self.__check_slow_replay(last_fname)
            # a replay task replay multiple times or a replay task replay one time slow.
        self.__finish()


def main(tenant_id, ls_id, end_time, interval, log_dir):
    checker = SlowReplayChecker(tenant_id, ls_id, end_time, interval, log_dir)
    checker.execute()


if __name__ == "__main__":
    now = datetime.now()
    parser = argparse.ArgumentParser(description='check replay stuck 4.x_v2')
    parser.add_argument('--tenant', type=int, dest='tenant', required=True, help='specify the tenant to be analysis')
    parser.add_argument('--ls', type=int, dest='ls', required=True, help='specify the ls to be analysis')
    parser.add_argument('--end_time', type=str, dest='end_time', default=str(now), help='time to end analysis, default now: ' + str(now))
    parser.add_argument('--log_dir', type=str, dest='log_dir', required=True, help='the observer log dir')
    parser.add_argument('--interval', type=int, dest='interval', default=60, help='the analysis interval, default 60 minutes')

    try:
        args = parser.parse_args()
        tenant = args.tenant
        ls = args.ls
        end_time = datetime.strptime(args.end_time, "%Y-%m-%d %H:%M:%S.%f")
        log_dir = args.log_dir
        interval = args.interval

        main(tenant, ls, end_time, interval, log_dir)
    except Exception as e:
        print(parser.print_help())
        print(str(e))
