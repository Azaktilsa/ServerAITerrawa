"""
Sistema de estadísticas y monitoreo de la aplicación
"""
import json
import os
from datetime import datetime
from typing import Dict, Any
import threading


class StatsManager:
    def __init__(self, stats_file: str = "app_stats.json"):
        self.stats_file = stats_file
        self.lock = threading.Lock()
        self._load_stats()

    def _load_stats(self):
        """Cargar estadísticas desde archivo"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    self.stats = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.stats = self._get_default_stats()
        else:
            self.stats = self._get_default_stats()

    def _get_default_stats(self) -> Dict[str, Any]:
        """Estadísticas por defecto"""
        return {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "requests_by_finca": {
                "CAMANOVILLO": 0,
                "EXCANCRIGRU": 0,
                "FERTIAGRO": 0,
                "GROVITAL": 0,
                "SUFAAZA": 0,
                "TIERRAVID": 0
            },
            "last_updated": datetime.now().isoformat(),
            "daily_stats": {},
            "uptime_start": datetime.now().isoformat()
        }

    def _save_stats(self):
        """Guardar estadísticas en archivo"""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            print(f"Error guardando estadísticas: {e}")

    def increment_total_requests(self):
        """Incrementar contador de solicitudes totales"""
        with self.lock:
            self.stats["total_requests"] += 1
            self._update_daily_stats("total")
            self.stats["last_updated"] = datetime.now().isoformat()
            self._save_stats()

    def increment_successful_requests(self, finca: str = None):
        """Incrementar contador de solicitudes exitosas"""
        with self.lock:
            self.stats["successful_requests"] += 1
            if finca and finca in self.stats["requests_by_finca"]:
                self.stats["requests_by_finca"][finca] += 1
            self._update_daily_stats("successful")
            self.stats["last_updated"] = datetime.now().isoformat()
            self._save_stats()

    def increment_failed_requests(self):
        """Incrementar contador de solicitudes fallidas"""
        with self.lock:
            self.stats["failed_requests"] += 1
            self._update_daily_stats("failed")
            self.stats["last_updated"] = datetime.now().isoformat()
            self._save_stats()

    def _update_daily_stats(self, stat_type: str):
        """Actualizar estadísticas diarias"""
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.stats["daily_stats"]:
            self.stats["daily_stats"][today] = {
                "total": 0,
                "successful": 0,
                "failed": 0
            }
        self.stats["daily_stats"][today][stat_type] += 1

    def get_success_rate(self) -> float:
        """Calcular tasa de éxito"""
        total = self.stats["total_requests"]
        if total == 0:
            return 100.0
        return round((self.stats["successful_requests"] / total) * 100, 1)

    def get_uptime_hours(self) -> int:
        """Calcular horas de funcionamiento"""
        start_time = datetime.fromisoformat(self.stats["uptime_start"])
        uptime = datetime.now() - start_time
        return int(uptime.total_seconds() / 3600)

    def get_today_stats(self) -> Dict[str, int]:
        """Obtener estadísticas del día actual"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.stats["daily_stats"].get(today, {
            "total": 0,
            "successful": 0,
            "failed": 0
        })

    def get_most_used_finca(self) -> str:
        """Obtener la finca más utilizada"""
        fincas = self.stats["requests_by_finca"]
        if not any(fincas.values()):
            return "N/A"
        return max(fincas, key=fincas.get)

    def get_all_stats(self) -> Dict[str, Any]:
        """Obtener todas las estadísticas"""
        return {
            "total_requests": self.stats["total_requests"],
            "successful_requests": self.stats["successful_requests"],
            "failed_requests": self.stats["failed_requests"],
            "success_rate": self.get_success_rate(),
            "uptime_hours": self.get_uptime_hours(),
            "today_stats": self.get_today_stats(),
            "most_used_finca": self.get_most_used_finca(),
            "requests_by_finca": self.stats["requests_by_finca"],
            "last_updated": self.stats["last_updated"]
        }


# Instancia global del gestor de estadísticas
stats_manager = StatsManager()
