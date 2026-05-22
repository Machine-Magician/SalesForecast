import papermill as pm
import os
from datetime import datetime

def run_batch(batch_num):
    """Запускает Jupyter ноутбук для указанного батча"""

    print(f"\n{'='*60}")
    print(f" ЗАПУСК БАТЧА №{batch_num}")
    print('='*60)

    # Путь к твоему ноутбуку
    notebook_path = '/home/jovyan/work/scripts/market_demand_klasters.ipynb'

    # Создаем папку для выходных файлов
    os.makedirs('/home/jovyan/work/notebooks/outputs', exist_ok=True)

    # Имя выходного файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = f'/home/jovyan/work/notebooks/outputs/batch_{batch_num}_{timestamp}.ipynb'

    # Запускаем ноутбук с параметром (ОДИН РАЗ!)
    pm.execute_notebook(
        notebook_path,
        output,
        parameters={'CURRENT_BATCH': batch_num},
        kernel_name='python3'  # если хочешь явно указать ядро
    )

    print(f" Результат сохранен: {output}")
    return output

# Для теста
if __name__ == "__main__":
    run_batch(1)