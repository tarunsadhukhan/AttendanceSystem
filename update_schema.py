"""Bring an old restored `sjm` backup up to what the current code expects.

Idempotent: safe to run repeatedly. Run ON the VPS (DB is not reachable
from outside):  python update_schema.py          # apply
               python update_schema.py --check  # report only, change nothing

Covers the 2026 schema drift this repo + the vowerp3be migrations introduced:
new columns, new tables the app does NOT self-create, and the three report
views. Tables the app already creates at startup (jute_mukam_recvd,
tbl_jute_received, assorting_entry, weight_tran, occupations, user_mst,
permissions tables) are left to the app.
"""
import sys

from db import get_db

CHECK_ONLY = "--check" in sys.argv

# ── tables the app does not self-create ──────────────────────────────
TABLES = {
    "tbl_whatsapp_send": """
        CREATE TABLE IF NOT EXISTS tbl_whatsapp_send (
            id        INT AUTO_INCREMENT PRIMARY KEY,
            name      VARCHAR(100)  DEFAULT NULL,
            mobno     VARCHAR(20)   DEFAULT NULL,
            from_msg  VARCHAR(255)  DEFAULT NULL,
            msg_for   VARCHAR(10)   DEFAULT NULL,
            email_id  VARCHAR(255)  DEFAULT NULL,
            sch_times VARCHAR(100)  DEFAULT NULL
        )
    """,
    "tbl_cont_widning_entry": """
        CREATE TABLE IF NOT EXISTS tbl_cont_widning_entry (
            cont_winding_ent_id INT AUTO_INCREMENT PRIMARY KEY,
            tran_date           DATE          DEFAULT NULL,
            quality_id          INT           DEFAULT NULL,
            prod_kgs            DECIMAL(12,2) DEFAULT NULL,
            updated_by          INT           DEFAULT NULL,
            update_date_time    TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP
        )
    """,
    "tbl_daily_summ_mechine_data": """
        CREATE TABLE IF NOT EXISTS tbl_daily_summ_mechine_data (
            daily_sum_mc_id INT AUTO_INCREMENT PRIMARY KEY,
            tran_date       DATE         DEFAULT NULL,
            branch_id       INT          DEFAULT NULL,
            mc_code_id      INT          DEFAULT NULL,
            spell_a1        DECIMAL(8,2) DEFAULT NULL,
            spell_a2        DECIMAL(8,2) DEFAULT NULL,
            spell_b1        DECIMAL(8,2) DEFAULT NULL,
            spell_b2        DECIMAL(8,2) DEFAULT NULL,
            spell_c         DECIMAL(8,2) DEFAULT NULL,
            shift_a         DECIMAL(8,2) DEFAULT NULL,
            shift_b         DECIMAL(8,2) DEFAULT NULL,
            shift_c         DECIMAL(8,2) DEFAULT NULL,
            is_active       TINYINT      DEFAULT 1,
            created_on      TIMESTAMP    NULL DEFAULT NULL
        )
    """,
    "designation_norms_mst": """
        CREATE TABLE IF NOT EXISTS designation_norms_mst (
            desig_norm_id  INT AUTO_INCREMENT PRIMARY KEY,
            desig_id       INT          DEFAULT NULL,
            shift_a        DECIMAL(8,2) DEFAULT NULL,
            shift_b        DECIMAL(8,2) DEFAULT NULL,
            shift_c        DECIMAL(8,2) DEFAULT NULL,
            fixed_variable CHAR(1)      DEFAULT 'F',
            active         TINYINT      DEFAULT 1
        )
    """,
    "mc_occu_link_mst": """
        CREATE TABLE IF NOT EXISTS mc_occu_link_mst (
            mc_occu_link_id INT AUTO_INCREMENT PRIMARY KEY,
            mc_id           INT          DEFAULT NULL,
            desig_id        INT          DEFAULT NULL,
            no_of_mcs       DECIMAL(8,2) DEFAULT NULL,
            no_of_hands     DECIMAL(8,2) DEFAULT NULL,
            active          TINYINT      DEFAULT 1
        )
    """,
    # same DDL the app uses in src/jute_mukam_recvd/jute_mukam_recvd.py
    "jute_mukam_recvd": """
        CREATE TABLE IF NOT EXISTS jute_mukam_recvd (
            jute_mukam_recvd     INT(11) NOT NULL AUTO_INCREMENT,
            jute_mukam_recvd_no  INT(11) DEFAULT NULL,
            recvd_date           DATE DEFAULT NULL,
            party_id             INT(11) DEFAULT NULL,
            mukam_id             INT(11) DEFAULT NULL,
            quality_id           INT(11) DEFAULT NULL,
            gross_weight         DECIMAL(10,3) DEFAULT NULL,
            tare_weight          DECIMAL(10,3) DEFAULT NULL,
            `net_weight(10,3)`   INT(11) DEFAULT NULL,
            geo_location         VARCHAR(100) DEFAULT NULL,
            geo_place            VARCHAR(255) DEFAULT NULL,
            remarks              VARCHAR(500) DEFAULT NULL,
            mukam_photo          LONGTEXT DEFAULT NULL,
            updated_by           INT(11) DEFAULT NULL,
            update_date_time     DATETIME DEFAULT NULL,
            PRIMARY KEY (jute_mukam_recvd),
            INDEX idx_jmr_no (jute_mukam_recvd_no)
        )
    """,
}

# ── columns added during 2026 on pre-existing tables ─────────────────
# (table, column, DDL after column name)
COLUMNS = [
    ("daily_attendance",            "shed_type",  "VARCHAR(20) DEFAULT 'Old Shed'"),
    ("daily_attendance",            "status_id",  "INT DEFAULT NULL"),

    ("attendance",                  "att_type",      "CHAR(1) DEFAULT 'R'"),
    ("attendance",                  "photo_att",     "LONGTEXT DEFAULT NULL"),
    ("attendance",                  "shift_hours",   "DECIMAL(5,2) DEFAULT 0"),
    ("attendance",                  "working_hours", "DECIMAL(5,2) DEFAULT 0"),
    ("attendance",                  "idle_hours",    "DECIMAL(5,2) DEFAULT 0"),

    ("mechine_code_master",         "shed_type", "VARCHAR(20) DEFAULT 'Old Shed'"),
    ("mechine_code_master",         "desig_id",  "INT DEFAULT NULL"),
    ("mechine_code_master",         "is_active", "TINYINT DEFAULT 1"),
    ("mechine_code_master",         "order_no",  "INT DEFAULT NULL"),

    ("tbl_daily_summ_mechine_data", "spell_a1",   "DECIMAL(8,2) DEFAULT NULL"),
    ("tbl_daily_summ_mechine_data", "spell_a2",   "DECIMAL(8,2) DEFAULT NULL"),
    ("tbl_daily_summ_mechine_data", "spell_b1",   "DECIMAL(8,2) DEFAULT NULL"),
    ("tbl_daily_summ_mechine_data", "spell_b2",   "DECIMAL(8,2) DEFAULT NULL"),
    ("tbl_daily_summ_mechine_data", "spell_c",    "DECIMAL(8,2) DEFAULT NULL"),
    ("tbl_daily_summ_mechine_data", "is_active",  "TINYINT DEFAULT 1"),
    ("tbl_daily_summ_mechine_data", "created_on", "TIMESTAMP NULL DEFAULT NULL"),

    ("tbl_whatsapp_send",           "msg_for",   "VARCHAR(10) DEFAULT NULL"),
    ("tbl_whatsapp_send",           "from_msg",  "VARCHAR(255) DEFAULT NULL"),
    ("tbl_whatsapp_send",           "email_id",  "VARCHAR(255) DEFAULT NULL"),
    ("tbl_whatsapp_send",           "sch_times", "VARCHAR(100) DEFAULT NULL"),

    ("jute_mukam_recvd",            "mukam_photo", "LONGTEXT DEFAULT NULL"),
    ("jute_mukam_recvd",            "geo_place",   "VARCHAR(255) DEFAULT NULL"),
    ("jute_mukam_recvd",            "remarks",     "VARCHAR(500) DEFAULT NULL"),

    ("dept_mst",                    "order_id", "INT DEFAULT NULL"),

    ("designation_mst",             "desig_code", "VARCHAR(20) DEFAULT NULL"),
    ("designation_mst",             "active",     "TINYINT DEFAULT 1"),

    ("designation_norms_mst",       "fixed_variable", "CHAR(1) DEFAULT 'F'"),
    ("designation_norms_mst",       "active",         "TINYINT DEFAULT 1"),
    ("mc_occu_link_mst",            "active",         "TINYINT DEFAULT 1"),
]

# ── report views (verbatim from sjmvowerp3be/dbqueries/migrations) ───
VIEWS = {
    "vw_man_machine": """
CREATE OR REPLACE VIEW `vw_man_machine` AS select `dm2`.`branch_id` AS `branch_id`,`dm2`.`dept_desc` AS `dept_desc`,`dm2`.`dept_code` AS `dept_code`,`dm`.`desig` AS `desig`,`dhn`.`attendance_date` AS `attendance_date`,`dhn`.`worked_designation_id` AS `worked_designation_id`,`dhn`.`hands_a` AS `hands_a`,`dhn`.`hands_b` AS `hands_b`,`dhn`.`hands_c` AS `hands_c`,`dhn`.`thands_a` AS `thands_a`,`dhn`.`thands_b` AS `thands_b`,`dhn`.`thands_c` AS `thands_c`,`dhn`.`fv` AS `fv`,`dhn`.`thands_a` - `dhn`.`hands_a` AS `extra_short_a`,`dhn`.`thands_b` - `dhn`.`hands_b` AS `extra_short_b`,`dhn`.`thands_c` - `dhn`.`hands_c` AS `extra_short_c` from (((select `da`.`attendance_date` AS `attendance_date`,`da`.`worked_designation_id` AS `worked_designation_id`,round(sum(case when `sm2`.`shift_name` = 'A' then `da`.`working_hours` else 0 end) / 8,2) AS `hands_a`,round(sum(case when `sm2`.`shift_name` = 'B' then `da`.`working_hours` else 0 end) / 8,2) AS `hands_b`,round(sum(case when `sm2`.`shift_name` = 'C' then `da`.`working_hours` else 0 end) / 8,2) AS `hands_c`,max(`dnm`.`shift_a`) AS `thands_a`,max(`dnm`.`shift_b`) AS `thands_b`,max(`dnm`.`shift_c`) AS `thands_c`,'F' AS `fv` from (((`daily_attendance` `da` left join `spell_mst` `sm` on(`sm`.`spell_name` = `da`.`spell`)) left join `shift_mst` `sm2` on(`sm`.`shift_id` = `sm2`.`shift_id`)) left join `designation_norms_mst` `dnm` on(`da`.`worked_designation_id` = `dnm`.`desig_id`)) where `da`.`branch_id` = 103 and `da`.`is_active` = 1 and `dnm`.`fixed_variable` = 'F' group by `da`.`attendance_date`,`da`.`worked_designation_id` union all select `da`.`attendance_date` AS `attendance_date`,`da`.`worked_designation_id` AS `worked_designation_id`,`da`.`hands_a` AS `hands_a`,`da`.`hands_b` AS `hands_b`,`da`.`hands_c` AS `hands_c`,`molm`.`thands_a` AS `thands_a`,`molm`.`thands_b` AS `thands_b`,`molm`.`thands_c` AS `thands_c`,'V' AS `fv` from ((select `da`.`attendance_date` AS `attendance_date`,`da`.`worked_designation_id` AS `worked_designation_id`,round(sum(case when `sm2`.`shift_name` = 'A' then `da`.`working_hours` else 0 end) / 8,2) AS `hands_a`,round(sum(case when `sm2`.`shift_name` = 'B' then `da`.`working_hours` else 0 end) / 8,2) AS `hands_b`,round(sum(case when `sm2`.`shift_name` = 'C' then `da`.`working_hours` else 0 end) / 8,2) AS `hands_c` from (((`daily_attendance` `da` left join `spell_mst` `sm` on(`sm`.`spell_name` = `da`.`spell`)) left join `shift_mst` `sm2` on(`sm`.`shift_id` = `sm2`.`shift_id`)) left join `designation_norms_mst` `dnm` on(`da`.`worked_designation_id` = `dnm`.`desig_id`)) where `da`.`branch_id` = 103 and `da`.`is_active` = 1 and `dnm`.`fixed_variable` = 'V' group by `da`.`attendance_date`,`da`.`worked_designation_id`) `da` left join (select `tdsmd`.`tran_date` AS `tran_date`,`molm`.`desig_id` AS `desig_id`,`tdsmd`.`mc_code_id` AS `mc_code_id`,`molm`.`no_of_mcs` AS `no_of_mcs`,`molm`.`no_of_hands` AS `no_of_hands`,`tdsmd`.`shift_a` AS `shift_a`,round(`tdsmd`.`shift_a` / `molm`.`no_of_mcs` * `molm`.`no_of_hands`,0) AS `thands_a`,round(`tdsmd`.`shift_b` / `molm`.`no_of_mcs` * `molm`.`no_of_hands`,0) AS `thands_b`,round(`tdsmd`.`shift_c` / `molm`.`no_of_mcs` * `molm`.`no_of_hands`,0) AS `thands_c` from (`tbl_daily_summ_mechine_data` `tdsmd` left join `mc_occu_link_mst` `molm` on(`tdsmd`.`mc_code_id` = `molm`.`mc_id`))) `molm` on(`da`.`worked_designation_id` = `molm`.`desig_id` and `da`.`attendance_date` = `molm`.`tran_date`)) union all select `molm`.`tran_date` AS `attendance_date`,`molm`.`desig_id` AS `worked_designation_id`,0 AS `hands_a`,0 AS `hands_b`,0 AS `hands_c`,`molm`.`thands_a` AS `thands_a`,`molm`.`thands_b` AS `thands_b`,`molm`.`thands_c` AS `thands_c`,'V' AS `fv` from (select `tdsmd`.`tran_date` AS `tran_date`,`molm`.`desig_id` AS `desig_id`,`tdsmd`.`mc_code_id` AS `mc_code_id`,`molm`.`no_of_mcs` AS `no_of_mcs`,`molm`.`no_of_hands` AS `no_of_hands`,`tdsmd`.`shift_a` AS `shift_a`,round(`tdsmd`.`shift_a` / `molm`.`no_of_mcs` * `molm`.`no_of_hands`,0) AS `thands_a`,round(`tdsmd`.`shift_b` / `molm`.`no_of_mcs` * `molm`.`no_of_hands`,0) AS `thands_b`,round(`tdsmd`.`shift_c` / `molm`.`no_of_mcs` * `molm`.`no_of_hands`,0) AS `thands_c` from (`tbl_daily_summ_mechine_data` `tdsmd` left join `mc_occu_link_mst` `molm` on(`tdsmd`.`mc_code_id` = `molm`.`mc_id`))) `molm` where `molm`.`desig_id` is not null and not exists (select 1 from (select `da`.`attendance_date` AS `attendance_date`,`da`.`worked_designation_id` AS `worked_designation_id`,round(sum(case when `sm2`.`shift_name` = 'A' then `da`.`working_hours` else 0 end) / 8,2) AS `hands_a`,round(sum(case when `sm2`.`shift_name` = 'B' then `da`.`working_hours` else 0 end) / 8,2) AS `hands_b`,round(sum(case when `sm2`.`shift_name` = 'C' then `da`.`working_hours` else 0 end) / 8,2) AS `hands_c` from (((`daily_attendance` `da` left join `spell_mst` `sm` on(`sm`.`spell_name` = `da`.`spell`)) left join `shift_mst` `sm2` on(`sm`.`shift_id` = `sm2`.`shift_id`)) left join `designation_norms_mst` `dnm` on(`da`.`worked_designation_id` = `dnm`.`desig_id`)) where `da`.`branch_id` = 103 and `da`.`is_active` = 1 and `dnm`.`fixed_variable` = 'V' group by `da`.`attendance_date`,`da`.`worked_designation_id`) `da` where `da`.`worked_designation_id` = `molm`.`desig_id` and `da`.`attendance_date` = `molm`.`tran_date`) ) `dhn` left join `designation_mst` `dm` on(`dhn`.`worked_designation_id` = `dm`.`designation_id`)) left join `dept_mst` `dm2` on(`dm2`.`dept_id` = `dm`.`dept_id`))
""",
    "vw_hands_report": """
CREATE OR REPLACE VIEW `vw_hands_report` AS
WITH machines AS (
    SELECT
        t.tran_date,
        t.branch_id,
        mc.desig_id AS designation_id,
        SUM(CASE WHEN mc.shed_type = 'Old Shed' THEN t.shift_a  ELSE 0 END)                     AS mh_a_os,
        SUM(CASE WHEN mc.shed_type = 'New Shed' THEN t.shift_a  ELSE 0 END)                     AS mh_a_ns,
        SUM(CASE WHEN mc.shed_type = 'Old Shed' THEN t.spell_b1 ELSE 0 END)                     AS mh_b1_os,
        SUM(CASE WHEN mc.shed_type = 'New Shed' THEN t.spell_b1 ELSE 0 END)                     AS mh_b1_ns,
        SUM(CASE WHEN mc.shed_type = 'Old Shed' THEN t.spell_b2 ELSE 0 END)                     AS mh_b2_os,
        SUM(CASE WHEN mc.shed_type = 'New Shed' THEN t.spell_b2 ELSE 0 END)                     AS mh_b2_ns,
        SUM(CASE WHEN mc.shed_type = 'Old Shed' THEN COALESCE(t.shift_c, t.spell_c) ELSE 0 END) AS mh_c_os,
        SUM(CASE WHEN mc.shed_type = 'New Shed' THEN COALESCE(t.shift_c, t.spell_c) ELSE 0 END) AS mh_c_ns
    FROM tbl_daily_summ_mechine_data t
    JOIN mechine_code_master mc ON mc.mc_code_id = t.mc_code_id
    WHERE COALESCE(t.is_active, 1) = 1
      AND mc.is_active = 1
      AND mc.desig_id IS NOT NULL
    GROUP BY t.tran_date, t.branch_id, mc.desig_id
),
hands AS (
    SELECT
        da.attendance_date        AS tran_date,
        da.branch_id,
        da.worked_designation_id  AS designation_id,
        SUM(CASE WHEN da.shed_type = 'Old Shed' AND da.spell IN ('A','A1','A2','GS') THEN da.working_hours ELSE 0 END) / 8 AS hands_a_os,
        SUM(CASE WHEN da.shed_type = 'New Shed' AND da.spell IN ('A','A1','A2','GS') THEN da.working_hours ELSE 0 END) / 8 AS hands_a_ns,
        SUM(CASE WHEN da.shed_type = 'Old Shed' AND da.spell IN ('B','B1')          THEN da.working_hours ELSE 0 END) / 8 AS hands_b1_os,
        SUM(CASE WHEN da.shed_type = 'New Shed' AND da.spell IN ('B','B1')          THEN da.working_hours ELSE 0 END) / 8 AS hands_b1_ns,
        SUM(CASE WHEN da.shed_type = 'Old Shed' AND da.spell IN ('B','B2')          THEN da.working_hours ELSE 0 END) / 8 AS hands_b2_os,
        SUM(CASE WHEN da.shed_type = 'New Shed' AND da.spell IN ('B','B2')          THEN da.working_hours ELSE 0 END) / 8 AS hands_b2_ns,
        SUM(CASE WHEN da.shed_type = 'Old Shed' AND da.spell IN ('C','C1')          THEN da.working_hours ELSE 0 END) / 8 AS hands_c_os,
        SUM(CASE WHEN da.shed_type = 'New Shed' AND da.spell IN ('C','C1')          THEN da.working_hours ELSE 0 END) / 8 AS hands_c_ns,
        SUM(CASE WHEN da.shed_type = 'Old Shed' THEN da.working_hours ELSE 0 END) / 8 AS hands_total_os,
        SUM(CASE WHEN da.shed_type = 'New Shed' THEN da.working_hours ELSE 0 END) / 8 AS hands_total_ns
    FROM daily_attendance da
    WHERE da.is_active = 1
    GROUP BY da.attendance_date, da.branch_id, da.worked_designation_id
),
universe AS (
    SELECT dt.tran_date, dt.branch_id, dg.designation_id
    FROM (
        SELECT DISTINCT attendance_date AS tran_date, branch_id
        FROM daily_attendance WHERE is_active = 1
        UNION
        SELECT DISTINCT tran_date, branch_id
        FROM tbl_daily_summ_mechine_data WHERE COALESCE(is_active, 1) = 1
    ) dt
    JOIN designation_mst dg ON dg.branch_id = dt.branch_id AND dg.active = 1
)
SELECT
    u.tran_date,
    u.branch_id,
    d.dept_id,
    dept.dept_desc,
    dept.dept_code,
    dept.order_id                       AS dept_order,
    u.designation_id,
    d.desig                             AS particular,
    d.desig_code,
    ord.row_order,
    ROUND(COALESCE(m.mh_a_os, 0),  2)   AS mh_a_os,   ROUND(COALESCE(h.hands_a_os, 0),  2) AS hands_a_os,
    ROUND(COALESCE(m.mh_a_ns, 0),  2)   AS mh_a_ns,   ROUND(COALESCE(h.hands_a_ns, 0),  2) AS hands_a_ns,
    ROUND(COALESCE(m.mh_b1_os, 0), 2)   AS mh_b1_os,  ROUND(COALESCE(h.hands_b1_os, 0), 2) AS hands_b1_os,
    ROUND(COALESCE(m.mh_b1_ns, 0), 2)   AS mh_b1_ns,  ROUND(COALESCE(h.hands_b1_ns, 0), 2) AS hands_b1_ns,
    ROUND(COALESCE(m.mh_b2_os, 0), 2)   AS mh_b2_os,  ROUND(COALESCE(h.hands_b2_os, 0), 2) AS hands_b2_os,
    ROUND(COALESCE(m.mh_b2_ns, 0), 2)   AS mh_b2_ns,  ROUND(COALESCE(h.hands_b2_ns, 0), 2) AS hands_b2_ns,
    ROUND(COALESCE(m.mh_c_os, 0),  2)   AS mh_c_os,   ROUND(COALESCE(h.hands_c_os, 0),  2) AS hands_c_os,
    ROUND(COALESCE(m.mh_c_ns, 0),  2)   AS mh_c_ns,   ROUND(COALESCE(h.hands_c_ns, 0),  2) AS hands_c_ns,
    ROUND(COALESCE(h.hands_total_os, 0) + COALESCE(h.hands_total_ns, 0), 2) AS total_hands
FROM universe u
LEFT JOIN machines m ON m.tran_date = u.tran_date AND m.branch_id = u.branch_id AND m.designation_id = u.designation_id
LEFT JOIN hands    h ON h.tran_date = u.tran_date AND h.branch_id = u.branch_id AND h.designation_id = u.designation_id
LEFT JOIN designation_mst d    ON d.designation_id = u.designation_id
LEFT JOIN dept_mst        dept ON dept.dept_id      = d.dept_id
LEFT JOIN (
    SELECT desig_id, MIN(order_no) AS row_order
    FROM mechine_code_master
    WHERE desig_id IS NOT NULL AND is_active = 1
    GROUP BY desig_id
) ord ON ord.desig_id = u.designation_id
""",
    "vw_hands_std_report": """
CREATE OR REPLACE VIEW `vw_hands_std_report` AS
WITH act AS (
    SELECT
        da.attendance_date       AS tran_date,
        da.branch_id,
        da.worked_designation_id AS designation_id,
        SUM(CASE WHEN da.spell IN ('A','A1','A2','GS') THEN da.working_hours ELSE 0 END) / 8 AS act_a,
        SUM(CASE WHEN da.spell IN ('B','B1','B2')      THEN da.working_hours ELSE 0 END) / 8 AS act_b,
        SUM(CASE WHEN da.spell IN ('C','C1')           THEN da.working_hours ELSE 0 END) / 8 AS act_c
    FROM daily_attendance da
    WHERE da.is_active = 1
    GROUP BY da.attendance_date, da.branch_id, da.worked_designation_id
),
std_f AS (
    SELECT desig_id AS designation_id, shift_a AS std_a, shift_b AS std_b, shift_c AS std_c
    FROM designation_norms_mst
    WHERE COALESCE(active, 1) = 1 AND fixed_variable = 'F'
),
std_v AS (
    SELECT
        t.tran_date,
        t.branch_id,
        mc.desig_id AS designation_id,
        SUM(t.shift_a                     / NULLIF(molm.no_of_mcs, 0) * molm.no_of_hands) AS std_a,
        SUM(t.shift_b                     / NULLIF(molm.no_of_mcs, 0) * molm.no_of_hands) AS std_b,
        SUM(COALESCE(t.shift_c, t.spell_c)/ NULLIF(molm.no_of_mcs, 0) * molm.no_of_hands) AS std_c
    FROM tbl_daily_summ_mechine_data t
    JOIN mechine_code_master mc   ON mc.mc_code_id = t.mc_code_id
                                 AND mc.is_active = 1 AND mc.desig_id IS NOT NULL
    JOIN mc_occu_link_mst    molm ON molm.mc_id = t.mc_code_id AND COALESCE(molm.active, 1) = 1
    WHERE COALESCE(t.is_active, 1) = 1
    GROUP BY t.tran_date, t.branch_id, mc.desig_id
),
universe AS (
    SELECT dt.tran_date, dt.branch_id, dg.designation_id
    FROM (
        SELECT DISTINCT attendance_date AS tran_date, branch_id
        FROM daily_attendance WHERE is_active = 1
        UNION
        SELECT DISTINCT tran_date, branch_id
        FROM tbl_daily_summ_mechine_data WHERE COALESCE(is_active, 1) = 1
    ) dt
    JOIN designation_mst dg ON dg.branch_id = dt.branch_id AND dg.active = 1
)
SELECT
    u.tran_date,
    u.branch_id,
    dg.dept_id,
    dept.dept_desc,
    dept.dept_code,
    u.designation_id,
    dg.desig       AS particular,
    dg.desig_code,
    ROUND(COALESCE(a.act_a, 0), 2)                               AS act_a,
    ROUND(COALESCE(sf.std_a, sv.std_a, 0), 2)                    AS std_a,
    ROUND(COALESCE(a.act_b, 0), 2)                               AS act_b,
    ROUND(COALESCE(sf.std_b, sv.std_b, 0), 2)                    AS std_b,
    ROUND(COALESCE(a.act_c, 0), 2)                               AS act_c,
    ROUND(COALESCE(sf.std_c, sv.std_c, 0), 2)                    AS std_c
FROM universe u
JOIN designation_mst dg ON dg.designation_id = u.designation_id
LEFT JOIN dept_mst dept  ON dept.dept_id = dg.dept_id
LEFT JOIN act   a  ON a.tran_date  = u.tran_date AND a.branch_id  = u.branch_id AND a.designation_id  = u.designation_id
LEFT JOIN std_f sf ON sf.designation_id = u.designation_id
LEFT JOIN std_v sv ON sv.tran_date = u.tran_date AND sv.branch_id = u.branch_id AND sv.designation_id = u.designation_id
""",
}

# every table the code references; reported (not created) if still absent
REFERENCED = [
    "assorting_entry", "attendance", "branch_mst", "co_mst",
    "daily_attendance", "daily_attendance_mod", "daily_doff_frames_winding",
    "daily_doff_tbl", "daily_ebmc_attendance", "dept_mst", "designation_mst",
    "designation_norms_mst", "emp_branch", "employee_face_mst",
    "employee_rate_table", "fne_master", "frame_details_mst",
    "hrms_ed_official_details", "hrms_ed_personal_details", "jute_mukam_mst",
    "jute_mukam_recvd", "jute_quality_mst", "leave_tran_details",
    "leave_transactions", "leave_types", "machine_mst", "mc_occu_link_mst",
    "mech_occu_link", "mechine_code_master", "occupations", "party_mst",
    "shift_mst", "spell_mst", "spinning_quality_mst", "spinning_type_mst",
    "sprd_jute_quality_mst", "status_mst", "sub_dept_mst",
    "tbl_cont_widning_entry", "tbl_customer_mst", "tbl_daily_bales_transaction",
    "tbl_daily_drawing", "tbl_daily_finishing", "tbl_daily_roll_stock",
    "tbl_daily_sperder", "tbl_daily_summ_mechine_data",
    "tbl_daily_vvfd_transaction", "tbl_drawing_mst", "tbl_finishing_quality_mst",
    "tbl_jute_received", "tbl_other_entries", "tbl_selector_mst",
    "tbl_whatsapp_send", "tbl_yarn_transaction", "trolly_mst", "user_mst",
    "winding_quality_master",
]

REPORT_CODES = ["SR", "HR", "DR", "MIS", "DSR", "OE", "S"]


def table_exists(cur, name):
    cur.execute("SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = %s", (name,))
    return cur.fetchone()[0] > 0


def column_exists(cur, table, column):
    cur.execute("SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = %s "
                "AND column_name = %s", (table, column))
    return cur.fetchone()[0] > 0


def main():
    db = get_db()
    cur = db.cursor()
    mode = "CHECK (no changes)" if CHECK_ONLY else "APPLY"
    print(f"=== update_schema: {mode} ===\n")

    print("-- tables --")
    for name, ddl in TABLES.items():
        if table_exists(cur, name):
            print(f"   ok      {name}")
        elif CHECK_ONLY:
            print(f"   MISSING {name} (would create)")
        else:
            cur.execute(ddl)
            db.commit()
            print(f"   CREATED {name}")

    print("\n-- columns --")
    for table, column, ddl in COLUMNS:
        if not table_exists(cur, table):
            print(f"   skip    {table}.{column} (table absent)")
            continue
        if column_exists(cur, table, column):
            print(f"   ok      {table}.{column}")
        elif CHECK_ONLY:
            print(f"   MISSING {table}.{column} (would add)")
        else:
            cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {ddl}")
            db.commit()
            print(f"   ADDED   {table}.{column}")

    # after the column pass so the clone inherits shed_type etc.
    print("\n-- daily_attendance_mod (edit-audit mirror) --")
    if table_exists(cur, "daily_attendance_mod"):
        print("   ok      daily_attendance_mod")
    elif not table_exists(cur, "daily_attendance"):
        print("   skip    daily_attendance_mod (daily_attendance absent)")
    elif CHECK_ONLY:
        print("   MISSING daily_attendance_mod (would clone from daily_attendance)")
    else:
        cur.execute("CREATE TABLE daily_attendance_mod LIKE daily_attendance")
        db.commit()
        print("   CREATED daily_attendance_mod (LIKE daily_attendance)")

    print("\n-- views --")
    for name, ddl in VIEWS.items():
        if CHECK_ONLY:
            print(f"   would CREATE OR REPLACE {name}")
        else:
            cur.execute(ddl)
            db.commit()
            print(f"   view    {name} created/replaced")

    print("\n-- referenced tables still missing (restore/create manually) --")
    missing = [t for t in REFERENCED if not table_exists(cur, t)]
    for t in missing:
        print(f"   !! {t}")
    if not missing:
        print("   none — all referenced tables present")

    print("\n-- report recipients (tbl_whatsapp_send.msg_for) --")
    if table_exists(cur, "tbl_whatsapp_send"):
        cur.execute("SELECT DISTINCT msg_for FROM tbl_whatsapp_send")
        have = {r[0] for r in cur.fetchall()}
        for code in REPORT_CODES:
            state = "ok" if code in have else "NO ROWS (add recipients or the report won't send)"
            print(f"   {code:4} {state}")

    cur.close()
    db.close()
    print("\ndone.")


if __name__ == "__main__":
    main()
