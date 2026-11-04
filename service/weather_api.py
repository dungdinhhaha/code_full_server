import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry
from datetime import datetime, timedelta

class WeatherAPIClient:
    def __init__(self, lat=10.873504, lon=106.790532):
        self.lat = lat
        self.lon = lon
        self.url = "https://api.open-meteo.com/v1/forecast"
        
        # Thiết lập cache tránh gọi API quá dày (expire sau 1 giờ)
        self.cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
        self.retry_session = retry(self.cache_session, retries=5, backoff_factor=0.2)
        self.openmeteo = openmeteo_requests.Client(session=self.retry_session)

    def get_weather_data(self):
        """
        Lấy dữ liệu thời tiết:
        - Tổng bức xạ & ET0 cả ngày hôm nay.
        - Dự báo Nhiệt độ & Độ ẩm tại các mốc +1h, +2h, +3h.
        """
        try:
            # 1. Cấu hình tham số API
            params = {
                "latitude": self.lat,
                "longitude": self.lon,
                "hourly": ["temperature_2m", "relative_humidity_2m", "shortwave_radiation", "et0_fao_evapotranspiration"],
                "timezone": "auto",
                "forecast_days": 1
            }

            # 2. Gọi API
            responses = self.openmeteo.weather_api(self.url, params=params)
            response = responses[0]
            hourly = response.Hourly()

            # 3. Chuyển đổi dữ liệu sang Pandas DataFrame
            times = pd.date_range(
                start=pd.to_datetime(hourly.Time() + response.UtcOffsetSeconds(), unit="s"),
                end=pd.to_datetime(hourly.TimeEnd() + response.UtcOffsetSeconds(), unit="s"),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            )
            
            df = pd.DataFrame({
                "datetime": times,
                "temp": hourly.Variables(0).ValuesAsNumpy(),
                "hum": hourly.Variables(1).ValuesAsNumpy(),
                "rad": hourly.Variables(2).ValuesAsNumpy(),
                "et0": hourly.Variables(3).ValuesAsNumpy()
            })

            # 4. Tính toán các giá trị tổng trong ngày
            total_rad = float(df['rad'].sum())
            total_et0 = float(df['et0'].sum())

            # 5. Lấy dữ liệu dự báo cho 3 mốc thời gian tới
            now = datetime.now().replace(minute=0, second=0, microsecond=0)
            
            # Hàm phụ để bốc dữ liệu an toàn từ DataFrame
            def get_row_data(target_time):
                row = df[df['datetime'] == target_time]
                if not row.empty:
                    return round(float(row.iloc[0]['temp']), 2), round(float(row.iloc[0]['hum']), 2)
                # Nếu không có (ví dụ cuối ngày), lấy dòng cuối cùng
                return round(float(df.iloc[-1]['temp']), 2), round(float(df.iloc[-1]['hum']), 2)

            t1h, h1h = get_row_data(now + timedelta(hours=1))
            t2h, h2h = get_row_data(now + timedelta(hours=2))
            t3h, h3h = get_row_data(now + timedelta(hours=3))

            # 6. Đóng gói kết quả
            return {
                "status": "success",
                "data": {
                    "lat": round(response.Latitude(), 4),
                    "lon": round(response.Longitude(), 4),
                    "total_radiation_day": round(total_rad, 2),
                    "total_et0_day": round(total_et0, 2),
                    "t1h": t1h, "h1h": h1h,
                    "t2h": t2h, "h2h": h2h,
                    "t3h": t3h, "h3h": h3h,
                    "current_sync_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
