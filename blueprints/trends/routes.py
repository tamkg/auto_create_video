from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file
from pytrends.request import TrendReq
import matplotlib.pyplot as plt
import io
import pandas as pd

trends_bp = Blueprint('trends', __name__, template_folder='templates')
pytrends = TrendReq(hl='en-US', tz=360)

@trends_bp.route('/trends', methods=['GET', 'POST'])
def google_trends():
    if request.method == 'POST':
        keywords = request.form.get('keywords')
        timeframe = request.form.get('timeframe', 'today 12-m')

        if not keywords:
            flash("Vui lòng nhập từ khóa để xem xu hướng.")
            return redirect(url_for('trends.google_trends'))

        keyword_list = [kw.strip() for kw in keywords.split(',')]
        pytrends.build_payload(keyword_list, cat=0, timeframe=timeframe, geo='', gprop='')

        # Lấy dữ liệu xu hướng
        trend_data = pytrends.interest_over_time()
        if trend_data.empty:
            flash("Không tìm thấy xu hướng cho từ khóa này.")
            return redirect(url_for('trends.google_trends'))

        # Xóa cột 'isPartial' nếu có
        if 'isPartial' in trend_data.columns:
            trend_data = trend_data.drop(columns=['isPartial'])

        # Tạo biểu đồ
        fig, ax = plt.subplots(figsize=(10, 6))
        for keyword in keyword_list:
            ax.plot(trend_data.index, trend_data[keyword], label=keyword)

        ax.set_title("Xu hướng tìm kiếm trên Google")
        ax.set_xlabel("Thời gian")
        ax.set_ylabel("Mức độ quan tâm")
        ax.legend()
        plt.tight_layout()

        # Lưu biểu đồ vào buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()

        return send_file(buf, mimetype='image/png')

    return render_template('trends/trends.html')
