from datetime import datetime, timedelta
import re
from os import listdir
from os.path import isfile, join
import os.path
import argparse
import logging

FORMAT = '%(asctime)-15s %(levelname)s %(module)s:%(filename)s:%(lineno)s %(funcName)s %(message)s'
logging.basicConfig(format=FORMAT, filename='smart_dev.log', filemode="w", level=logging.INFO)
logger = logging.getLogger('smart_dev')

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
        t = None
        if m:
            t = datetime.strptime(m.group('date_time'), "%Y-%m-%d %H:%M:%S.%f")
        else:
            print("parse_log_time failed", line)
        return t

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
        special_file_path = join(filedir, special_file)
        if os.path.exists(special_file_path):
            log_time = LOGFileCommonUtil.get_first_log_time(special_file_path)
            if log_time >= start_time and log_time <= end_time:
                res.append(special_file)
        return res


class CLOGCommonUtil:
    @staticmethod
    def scn_to_datetime(scn):
        return datetime.fromtimestamp(float(scn) / 1000000000)


class CLOGDiskFullErrorLog:
    @staticmethod
    def is_clog_disk_full_error_log(line):
        p = "Log out of disk space"
        res = line.find(p)
        return res >= 0

    @staticmethod
    def parse_clog_disk_full_error_log(line):
        d = dict()
        # oldest_log_stream=1001
        t_d = CommonUtil.parse_kv_s_i(line)
        d.update(t_d)
        # total_size(MB)=22118
        p = "(?P<key>\w+\(\w+\))=(?P<value>\d+)"
        m = re.finditer(p, line)
        for i in m:
            d[i.group('key')] = int(i.group('value'))
        # used_percent(%)=92
        p = "(?P<key>\w+\(%\))=(?P<value>\d+)"
        m = re.finditer(p, line)
        for i in m:
            d[i.group('key')] = int(i.group('value'))
        # oldest_scn=\{val:(?P<oldest_scn>\d+)\}
        p = "oldest_scn=\{val:(?P<oldest_scn>\d+)\}"
        p1 = "oldest_scn=\{val:(?P<oldest_scn>\d+"
        m = re.search(p, line)
        if not m:
            m = re.search(p1, line)
        d['oldest_scn'] = int(m.group('oldest_scn'))
        return d

    @staticmethod
    def parse_oldest_ls_id(line):
        d = CLOGDiskFullErrorLog.parse_clog_disk_full_error_log(line)
        return d['oldest_log_stream']

    @staticmethod
    def parse_oldest_scn(line):
        d = CLOGDiskFullErrorLog.parse_clog_disk_full_error_log(line)
        return d['oldest_scn']


ss = 'observer.log.20230225144757584:80184:[2023-02-25 11:33:29.492383] INFO  [STORAGE] update_clog_checkpoint (ob_checkpoint_executor.cpp:158) [69365][T1014_TxCkpt][T1014][Y0-0000000000000000-0-0] [lt=9] [CHECKPOINT] clog checkpoint no change(checkpoint_scn={val:1677245351996735693}, checkpoint_scn_in_ls_meta={val:1677245351996735693}, ls_id={id:1001}, service_type="TRANS_SERVICE")'
ss1 = '[2023-06-14 19:54:30.505462] INFO  [STORAGE] update_clog_checkpoint (ob_checkpoint_executor.cpp:158) [49723][T1004_CKClogDis][T1004][Y0-0000000000000000-0-0] [lt=46] [CHECKPOINT] clog checkpoint no change(checkpoint_scn={val:1686729660929049360, v:0}, checkpoint_scn_in_ls_meta={val:1686729660929049360, v:0}, ls_id={id:1001}, service_type="MAX_DECIDED_SCN")'


class CHECKPOINTCheckPointNoChangeLog:
    @staticmethod
    def is_clog_checkpoint_no_change_log(line):
        p = "clog checkpoint no change"
        res = line.find(p)
        return res >= 0

    @staticmethod
    def parse_checkpoint_scn(line):
        p = "checkpoint_scn=\{val:(?P<checkpoint_scn>\d+)\},"
        p1 = "checkpoint_scn=\{val:(?P<checkpoint_scn>\d+),"
        m = re.search(p, line)
        if not m:
            m = re.search(p1, line)
        scn = 0
        if m:
            scn = int(m.group('checkpoint_scn'))
        else:
            print("parse_checkpoint_scn failed", line)
        return scn

    @staticmethod
    def is_clog_checkpoint_stuck(line):
        # we think the checkpoint should not stuck for 2 min
        stuck_delta = timedelta(minutes=2)
        log_time = CommonUtil.parse_log_time(line)
        checkpoint_scn = CHECKPOINTCheckPointNoChangeLog.parse_checkpoint_scn(line)
        scn_time = CLOGCommonUtil.scn_to_datetime(checkpoint_scn)

        return log_time - scn_time > stuck_delta

    @staticmethod
    def get_stuck_mod(line):
        d = CommonUtil.parse_kv_s_s(line)
        return d['service_type']


sss = 'observer.log.20230228121145122:17812:[2023-02-28 12:11:42.802700] INFO  [STORAGE.TRANS] get_rec_scn (ob_ls_tx_service.cpp:441) [23277][T1293_CKClogDis][T1293][Y0-0000000000000000-0-0] [lt=7] [CHECKPOINT] ObLSTxService::get_rec_scn(common_checkpoint_type="TX_DATA_MEMTABLE_TYPE", common_checkpoints_[min_rec_scn_common_checkpoint_type_index]={ObIMemtableMgr:{Memtables:this:0x7f553bde21b0, ref_cnt:1, is_inited:true, tablet_id:{id:49402}, freezer:0x7f553bdedd10, table_type:1, memtable_head:13, memtable_tail:14, t3m:0x7f4a9f7dc030, tables:[null, null, null, null, null, null, null, null, null, null, null, null, null, 0x7f5c303e0b00, null, null]}, is_freezing:false, ls_id:{id:1}, tx_data_table:0x7f553bdef110, ls_tablet_svr:0x7f553bde2190, slice_allocator:0x7f553bdef150}, min_rec_scn={val:1677557329358828250}, ls_id_={id:1})'


class CHECKPOINTMinTransCheckpointTypeLog:
    @staticmethod
    def is_min_tx_checkpoint_log(line):
        p = "ObLSTxService::get_rec_scn"
        res = line.find(p)
        return res >= 0

    @staticmethod
    def parse_min_checkpoint_scn(line):
        p = "min_rec_scn=\{val:(?P<checkpoint_scn>\d+)\},"
        p1 = "min_rec_scn=\{val:(?P<checkpoint_scn>\d+),"
        m = re.search(p, line)
        if not m:
            m = re.search(p1, line)
        scn = 0
        if m:
            scn = int(m.group('checkpoint_scn'))
        else:
            print("parse_min_checkpoint_scn failed", line)
        return scn

    @staticmethod
    def get_stuck_mod(line):
        d = CommonUtil.parse_kv_s_s(line)
        return d['common_checkpoint_type']


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
        scn = 0
        if m:
            scn = int(m.group('scn'))
        else:
            print("parse_replay_scn failed", line)
        return scn

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


s_mt_destroy = 'observer.log.20230228200944475:274432:[2023-02-28 20:09:38.875418] INFO  [STORAGE] destroy (ob_memtable.cpp:218) [364755][T1002_T3mGC][T1002][Y0-0000000000000000-0-0] [lt=11] memtable destroyed(*this={ObITable:{this:0x7f2741f04c60, key:{tablet_id:{id:1152921504606878597}, column_group_idx:0, table_type:"MEMTABLE", scn_range:{start_scn:{val:1677586061370714713}, end_scn:{val:1677586077813599884}}}, ref_cnt:0, upper_trans_version:9223372036854775807, timestamp:1677586096236146}, this:0x7f2741f04c60, timestamp:1677586096236146, state:0, freeze_clock:17, max_schema_version:0, write_ref_cnt:0, local_allocator:{ListHandle:{freeze_stat:2, id:5902, clock:44648366080}, host:0x7f2743960030, arena_handle:{allocated:12582912}, last_freeze_timestamp:1677585793474860}, unsubmitted_cnt:0, unsynced_cnt:0, logging_blocked:false, unset_active_memtable_logging_blocked:false, resolve_active_memtable_left_boundary:true, contain_hotspot_row:false, max_end_scn:{val:1677586077813599884}, rec_scn:{val:1677586073254369954}, snapshot_version:{val:1677586077813599881}, migration_clog_checkpoint_scn:{val:0}, is_tablet_freeze:false, is_force_freeze:false, contain_hotspot_row:false, read_barrier:true, is_flushed:true, freeze_state:3, mt_stat_.frozen_time:1677586099599541, mt_stat_.ready_for_flush_time:1677586099604467, mt_stat_.create_flush_dag_time:1677586104195925, mt_stat_.release_time:1677586106328781, mt_stat_.last_print_time:0})'


class MemtableDestroyLog:
    @staticmethod
    def is_memtable_destroy_log(line):
        p = "memtable destroyed"
        res = line.find(p)
        return res >= 0

    @staticmethod
    def parse_mtstat(line):
        # >>> m.groupdict()
        # {'frozen_time': '1677586099599541', 'ready_for_flush_time': '1677586099604467', 'create_flush_dag_time': '1677586104195925', 'release_time': '1677586106328781'}
        d = dict()
        p = "mt_stat_.frozen_time:(?P<frozen_time>\d+),.*" + "mt_stat_.ready_for_flush_time:(?P<ready_for_flush_time>\d+),.*" + "mt_stat_.create_flush_dag_time:(?P<create_flush_dag_time>\d+),.*" + "mt_stat_.release_time:(?P<release_time>\d+)"
        m = re.search(p, line)
        d = m.groupdict()
        for k in d.keys():
            d[k] = CommonUtil.timestamp_to_datetime(d[k])
        return d

    @staticmethod
    def is_ready_for_flush_stuck(data):
        stuck_delta = timedelta(minutes=1)
        return data['ready_for_flush_time'] - data['frozen_time'] > stuck_delta

    @staticmethod
    def is_dump_stuck(data):
        stuck_delta = timedelta(minutes=1)
        return data['release_time'] - data['ready_for_flush_time'] > stuck_delta


class OutOfDiskErrorLog:
    @staticmethod
    def is_out_of_disk_log(line):
        p = "Failed to alloc block from io device"
        res = line.find(p)
        return res >= 0


class TooMaynySStableLog:
    @staticmethod
    def is_me(line):
        p = "Too many sstables in tablet, cannot schdule mini compaction, retry later"
        res = line.find(p)
        return res >= 0


class MemstoreFullChecker:
    PREFIX = '[BUGDETECT] '
    ENDL = '\n'
    NEXT_SEC = '\n\n'

    def __init__(self, tenant_id, start_check_time, interval=60, log_dir_path='./', res_file='result.txt'):
        self.res_file = res_file
        self.log_dir_path = log_dir_path
        self.interval = interval
        self.step = 1
        self.tenant_id = tenant_id
        self.rfd = None  # the result file fd
        self.log_time = start_check_time
        self.need_check_log_files = None  # the log file that need to be examed

    def __prepare(self):
        # open the result file
        self.rfd = open('result.txt', 'w')
        self.rfd.write(self.PREFIX + str(self.step) + ' ANALYZE DISK FULL:' + self.ENDL)
        self.rfd.write('tenant_id:{tenant_id}, log_time:{log_time}, interval:{interval}'.format(tenant_id=self.tenant_id, log_time=self.log_time, interval=self.interval) + self.ENDL)
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
        msg = "check file {fname}, with func {func}".format(fname=fname, func=check_func.func_name)
        logger.info(msg)
        exist_log = False
        if fname:
            f = open(join(self.log_dir_path, fname), 'r')
            for line in f:
                if not CommonUtil.is_tenant_log(self.tenant_id, line):
                    continue
                elif not check_func(line):
                    continue
                else:
                    exist_log = True
            f.close()
        return exist_log

    def __check_replay_stuck(self, fname):
        msg = "check file {fname}".format(fname=fname)
        logger.info(msg)
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
        ls_id = 0

        if fname:
            f = open(join(self.log_dir_path, fname), 'r')
            for line in f:
                if not CommonUtil.is_tenant_log(self.tenant_id, line):
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
                if is_replay_stuck:
                    ls_id = CommonUtil.parse_ls_id(line)
                    break
            f.close()
        if not exist_log:
            self.rfd.write('THERE IS NO REPLAY POINT LOG AT FILE: {fname}'.format(fname=fname) + self.ENDL)
        elif not is_follower:
            self.rfd.write('THE LS IS LEADER: {ls_id}'.format(ls_id=ls_id) + self.ENDL)
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

    def __check_dump_stuck(self, fname):
        msg = "check file {fname}".format(fname=fname)
        logger.info(msg)
        self.rfd.write(self.PREFIX + str(self.step) + ' DETECT WHETHER MEMTABLE DUMP STUCK:' + self.ENDL)
        while not self.__check_exist_log(MemtableDestroyLog.is_memtable_destroy_log, fname):
            fname = self.__next_log_file(fname)
            if not fname:
                break

        exist_log = False
        is_ready_for_flush_stuck = False
        is_dump_stuck = False
        mt_stat_dict = dict()
        if fname:
            f = open(join(self.log_dir_path, fname), 'r')
            for line in f:
                if not CommonUtil.is_tenant_log(self.tenant_id, line):
                    continue
                elif not MemtableDestroyLog.is_memtable_destroy_log(line):
                    continue
                else:
                    exist_log = True
                    mt_stat_dict = MemtableDestroyLog.parse_mtstat(line)
                    if not is_ready_for_flush_stuck and MemtableDestroyLog.is_ready_for_flush_stuck(mt_stat_dict):
                        is_ready_for_flush_stuck = True
                        self.rfd.write('MEMTABLE READY FOR FLUSH IS STUCK' + self.ENDL)
                        self.rfd.write(
                            'READY_FOR_FLUSH_TIME:{ready_time}, FREEZE_TIME:{freeze_time}, GAP:{gap}'.format(
                                ready_time=str(mt_stat_dict['ready_for_flush_time']), freeze_time=str(mt_stat_dict['frozen_time']), gap=str(mt_stat_dict['release_time'] - mt_stat_dict['frozen_time'])
                            )
                            + self.ENDL
                        )
                        self.rfd.write(line + self.ENDL)
                    if not is_dump_stuck and MemtableDestroyLog.is_dump_stuck(mt_stat_dict):
                        is_dump_stuck = True
                        self.rfd.write('MEMTABLE DUMP IS STUCK' + self.ENDL)
                        self.rfd.write(
                            'READY_FOR_FLUSH_TIME:{ready_time}, RELEASE_TIME:{release_time}, GAP:{gap}'.format(
                                ready_time=str(mt_stat_dict['ready_for_flush_time']), release_time=str(mt_stat_dict['release_time']), gap=str(mt_stat_dict['release_time'] - mt_stat_dict['ready_for_flush_time'])
                            )
                            + self.ENDL
                        )
                        self.rfd.write(line + self.ENDL)
                    if is_ready_for_flush_stuck and is_dump_stuck:
                        break
            f.close()
        if not exist_log:
            self.rfd.write('THERE IS NO MEMTABLE DESTROY LOG AT FILE: {fname}'.format(fname=fname) + self.ENDL)
        if exist_log and not is_ready_for_flush_stuck and not is_dump_stuck:
            self.rfd.write('MEMTABLE DUMP NOT STUCK AT LOG FILE: {fname}'.format(fname=fname) + self.ENDL)

        self.rfd.write(self.NEXT_SEC)
        self.step = self.step + 1

        return fname, exist_log, is_ready_for_flush_stuck, is_dump_stuck

    def __check_data_disk_full(self, fname):
        msg = "check file {fname}".format(fname=fname)
        logger.info(msg)
        is_disk_full = False
        self.rfd.write(self.PREFIX + str(self.step) + ' DETECT WHETHER DATA DISK FULL:' + self.ENDL)
        if fname:
            f = open(join(self.log_dir_path, fname), 'r')
            for line in f:
                if not CommonUtil.is_tenant_log(self.tenant_id, line):
                    continue
                elif not OutOfDiskErrorLog.is_out_of_disk_log(line):
                    continue
                else:
                    if not is_disk_full:
                        is_disk_full = True
                        self.rfd.write('SERVER DATA DISK FULL' + self.ENDL)
                        self.rfd.write(line + self.ENDL)
                        break
            if not is_disk_full:
                self.rfd.write('THERE IS NO DATA DISK FULL LOG AT FILE: {fname}'.format(fname=fname) + self.ENDL)

            f.close()
        else:
            self.rfd.write('THERE IS NO MORE LOG FILE: {fname}'.format(fname=fname) + self.ENDL)
        self.rfd.write(self.NEXT_SEC)
        self.step = self.step + 1

    def __check_too_many_sstable(self, fname):
        msg = "check file {fname}".format(fname=fname)
        logger.info(msg)
        is_too_many = False
        self.rfd.write(self.PREFIX + str(self.step) + ' DETECT TOO MANY SSTABLE:' + self.ENDL)

        if fname:
            f = open(join(self.log_dir_path, fname), 'r')
            for line in f:
                if not CommonUtil.is_tenant_log(self.tenant_id, line):
                    continue
                elif not TooMaynySStableLog.is_me(line):
                    continue
                else:
                    if not is_too_many:
                        is_too_many = True
                        self.rfd.write('TOO MANY SSTABLE ' + self.ENDL)
                        self.rfd.write(line + self.ENDL)
                        break
            if not is_too_many:
                self.rfd.write('THERE IS NO TOO MANY SSTABLE LOG AT FILE: {fname}'.format(fname=fname) + self.ENDL)

            f.close()
        else:
            self.rfd.write('THERE IS NO MORE LOG FILE: {fname}'.format(fname=fname) + self.ENDL)
        self.rfd.write(self.NEXT_SEC)
        self.step = self.step + 1

    def execute(self):
        self.__prepare()
        is_dump_stuck = False
        is_replay_stuck = False
        exist_log = False
        is_ready_for_flush_stuck = False

        # 1. get log file
        self.__get_log_files()

        # begin check a log file
        last_fname = ''
        if self.need_check_log_files:
            last_fname = self.need_check_log_files[0]
        if last_fname:
            print(last_fname)
            # 2. check disk full?
            print("self.__check_data_disk_full")
            self.__check_data_disk_full(last_fname)

            # 3. check too many sstable?
            print("self.__check_too_many_sstable")
            self.__check_too_many_sstable(last_fname)

            # 4. check dump stuck?
            last_fname, exist_log, is_ready_for_flush_stuck, is_dump_stuck = self.__check_dump_stuck(last_fname)

            # 5. check replay stuck?
            print("self.__check_replay_stuck")
            if not is_ready_for_flush_stuck:
                pass
            else:
                last_fname, is_replay_stuck = self.__check_replay_stuck(last_fname)


def main(tenant, end_time, interval, log_dir):
    checker = MemstoreFullChecker(tenant, end_time, interval, log_dir)
    checker.execute()


if __name__ == "__main__":
    now = datetime.now()
    parser = argparse.ArgumentParser(description='check memstore full 4.x')
    parser.add_argument('--tenant', type=int, dest='tenant', required=True, help='specify the tenant to be analysis')
    parser.add_argument('--end_time', type=str, dest='end_time', default=str(now), help='time to end analysis, default now: ' + str(now))
    parser.add_argument('--log_dir', type=str, dest='log_dir', required=True, help='the observer log dir')
    parser.add_argument('--interval', type=int, dest='interval', default=10, help='the analysis interval, default 10 minutes')

    try:
        args = parser.parse_args()
        tenant = args.tenant
        end_time = datetime.strptime(args.end_time, "%Y-%m-%d %H:%M:%S.%f")
        log_dir = args.log_dir
        interval = args.interval

        main(tenant, end_time, interval, log_dir)
    except Exception as e:
        print(parser.print_help())
        print(str(e))
