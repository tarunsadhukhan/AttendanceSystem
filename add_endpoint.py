#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script to add the winding-entry-2-quality-shift-report endpoint to doff.py
"""

endpoint_code = '''

# ══════════════════════════════════════════════════════════════════
# WINDING ENTRY 2 - QUALITY-WISE SHIFT-WISE REPORT
# ══════════════════════════════════════════════════════════════════

@doff_bp.route('/doff/winding-entry-2-quality-shift-report', methods=['GET'])
def winding_entry2_quality_shift_report():
    """Quality-wise Shift-wise production report for Winding Entry (2).
    
    Returns quality-wise breakdown with shift A/B/C totals for a given date+branch.
    
    Query params:
      ?date=YYYY-MM-DD  (required)
      ?branch_id=<id>   (required)
    
    Response:
      {
        status: 'success',
        report: [{
          quality_name: str,
          shift_a: float,
          shift_b: float,
          shift_c: float,
          total: float
        }],
        grand_total: {
          shift_a: float,
          shift_b: float,
          shift_c: float,
          total: float
        }
      }
    """
    d = request.args.get('date')
    branch_id = request.args.get('branch_id', type=int)
    
    if not d:
        return jsonify({'status': 'error', 'message': 'date is required'}), 400
    if not branch_id:
        return jsonify({'status': 'error', 'message': 'branch_id is required'}), 400
    
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        
        # Query: Get quality-wise shift-wise totals
        # Note: Using wng_quality from winding_quality_master table
        cur.execute("""
            SELECT 
                COALESCE(q.wng_quality, 'Unknown') AS quality_name,
                COALESCE(SUM(CASE WHEN s.spell_name LIKE '%%A%%' THEN w.net_weight ELSE 0 END), 0) AS shift_a,
                COALESCE(SUM(CASE WHEN s.spell_name LIKE '%%B%%' THEN w.net_weight ELSE 0 END), 0) AS shift_b,
                COALESCE(SUM(CASE WHEN s.spell_name LIKE '%%C%%' THEN w.net_weight ELSE 0 END), 0) AS shift_c,
                COALESCE(SUM(w.net_weight), 0) AS total
            FROM daily_doff_frames_winding w
            LEFT JOIN spell_mst s ON w.spell_id = s.spell_id
            LEFT JOIN winding_quality_master q ON w.quality_id = q.wng_quality_mst_id
            WHERE w.tran_date = %s
              AND w.branch_id = %s
              AND w.spg_wdg = 'W'
              AND w.net_weight IS NOT NULL
              AND (w.active IS NULL OR w.active = 1)
            GROUP BY q.wng_quality
            ORDER BY q.wng_quality
        """, (d, branch_id))
        
        report_rows = cur.fetchall()
        
        # Calculate grand totals
        grand_total_a = sum(float(row['shift_a'] or 0) for row in report_rows)
        grand_total_b = sum(float(row['shift_b'] or 0) for row in report_rows)
        grand_total_c = sum(float(row['shift_c'] or 0) for row in report_rows)
        grand_total = sum(float(row['total'] or 0) for row in report_rows)
        
        # Convert to float for JSON serialization
        for row in report_rows:
            row['shift_a'] = float(row['shift_a'] or 0)
            row['shift_b'] = float(row['shift_b'] or 0)
            row['shift_c'] = float(row['shift_c'] or 0)
            row['total'] = float(row['total'] or 0)
        
        cur.close()
        db.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Quality-wise shift-wise report generated',
            'report': report_rows,
            'grand_total': {
                'shift_a': grand_total_a,
                'shift_b': grand_total_b,
                'shift_c': grand_total_c,
                'total': grand_total
            }
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500
'''

# Read the existing file with UTF-8 encoding
with open('src/doff/doff.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Append the new endpoint
with open('src/doff/doff.py', 'a', encoding='utf-8') as f:
    f.write(endpoint_code)

print("✓ Endpoint added successfully!")

