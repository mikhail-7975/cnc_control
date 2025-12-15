"""
Пример создания и запуска пайплайна оптической инспекции компонентов.

Этот скрипт демонстрирует полный цикл работы пайплайна:
1. Загрузка эталонных и контрольных изображений
2. Загрузка разметки и маппинга
3. Подготовка эталона (создание кропов компонентов)
4. Подготовка контроля (выравнивание и создание кропов)
5. Запуск инспекции компонентов
6. Вывод результатов
"""
import json
from pathlib import Path

from cnc_control.core.pipeline.pipeline_runner import InspectionRunner
from example_pipeline_usage import load_etalon_images_from_folder


def main():
    """Основная функция запуска пайплайна инспекции."""
    print("=" * 60)
    print("Запуск пайплайна оптической инспекции компонентов")
    print("=" * 60)
    
    # Пути к данным
    etalon_folder = Path("data/plate_3/etalon_2/images")
    control_folder = Path("data/plate_3/control_4/images")
    bboxes_file = Path("markup_info/bboxes.json")
    etalon_mapping_file = Path("markup_info/etalon_mapping_upd.json")
    
    # Проверяем наличие файлов и папок
    print("\n1. Проверка наличия данных...")
    if not etalon_folder.exists():
        print(f"   ✗ Папка с эталонными изображениями не найдена: {etalon_folder}")
        return
    
    if not control_folder.exists():
        print(f"   ✗ Папка с контрольными изображениями не найдена: {control_folder}")
        return
    
    if not bboxes_file.exists():
        print(f"   ✗ Файл разметки не найден: {bboxes_file}")
        return
    
    if not etalon_mapping_file.exists():
        print(f"   ✗ Файл маппинга не найден: {etalon_mapping_file}")
        return
    
    print(f"   ✓ Папка с эталонными изображениями: {etalon_folder}")
    print(f"   ✓ Папка с контрольными изображениями: {control_folder}")
    print(f"   ✓ Файл разметки: {bboxes_file}")
    print(f"   ✓ Файл маппинга: {etalon_mapping_file}")
    
    # Создаем runner
    print("\n2. Инициализация InspectionRunner...")
    runner = InspectionRunner()
    print("   ✓ InspectionRunner создан")
    print(f"   ✓ Доступные алгоритмы инспекции: {list(runner.inspection_algorithms.keys())}")
    
    # Загружаем эталонные изображения
    print("\n3. Загрузка эталонных изображений...")
    etalon_images_dict = load_etalon_images_from_folder(str(etalon_folder))
    
    if not etalon_images_dict:
        print(f"   ✗ Не найдено эталонных изображений в папке {etalon_folder}")
        return
    
    print(f"   ✓ Загружено {len(etalon_images_dict)} эталонных изображений")
    runner.set_etalon_images(etalon_images_dict)
    
    # Загружаем контрольные изображения
    print("\n4. Загрузка контрольных изображений...")
    control_images_dict = load_etalon_images_from_folder(str(control_folder))
    
    if not control_images_dict:
        print(f"   ✗ Не найдено контрольных изображений в папке {control_folder}")
        return
    
    print(f"   ✓ Загружено {len(control_images_dict)} контрольных изображений")
    runner.set_control_images(control_images_dict)
    
    # Загружаем разметку
    print("\n5. Загрузка разметки...")
    with open(bboxes_file, 'r', encoding='utf-8') as f:
        markup = json.load(f)
    runner.set_etalon_markup(markup)
    print(f"   ✓ Загружена разметка для {len(markup)} изображений")
    
    # Загружаем маппинг
    print("\n6. Загрузка маппинга эталон-контроль...")
    runner.set_etalon_control_mapping()
    print(f"   ✓ Загружен маппинг: {len(runner.etalon_control_mapping)} записей")
    
    # Подготавливаем эталон
    print("\n7. Подготовка эталона...")
    runner.prepare_etalon()
    print(f"   ✓ Создано {len(runner.board_storage.etalon_components)} эталонных компонентов")
    
    # Подготавливаем контроль
    print("\n8. Подготовка контроля...")
    runner.prepare_control()
    print(f"   ✓ Выровнено {len(runner.board_storage.aligned_control_images)} контрольных изображений")
    print(f"   ✓ Создано {len(runner.board_storage.control_components)} контрольных компонентов")
    
    # Запускаем инспекцию
    print("\n9. Запуск инспекции компонентов...")
    runner.run_inspection()
    
    # Выводим статистику результатов
    print("\n10. Статистика результатов инспекции...")
    if runner.board_storage.inspection_results:
        total_results = len(runner.board_storage.inspection_results)
        missing_results = sum(1 for r in runner.board_storage.inspection_results.values() 
                           if r['result'] == 'missing')
        shifted_results = sum(1 for r in runner.board_storage.inspection_results.values() 
                              if r['result'] == 'shifted')
        ok_results = sum(1 for r in runner.board_storage.inspection_results.values() 
                        if r['result'] == 'ok')
        
        print(f"   ✓ Всего проверок: {total_results}")
        print(f"   ✓ Не дефект: {ok_results}")
        print(f"   ✓ Отсутствие: {missing_results}")
        print(f"   ✓ Смещение: {shifted_results}")
        
        # Показываем примеры результатов
        print("\n   Примеры результатов инспекции:")
        count = 0
        for inspection_id, result_data in runner.board_storage.inspection_results.items():
            if count >= 5:  # Показываем первые 5
                break
            print(f"     - {inspection_id}: {result_data['result']} (алгоритм: {result_data['algorithm']})")
            count += 1
    else:
        print("   ⚠ Результаты инспекции отсутствуют")
    
    print("\n" + "=" * 60)
    print("✓ Пайплайн завершен успешно!")
    print("=" * 60)
    
    # Возвращаем runner для дальнейшего использования результатов
    return runner


if __name__ == "__main__":
    runner = main()
    
    # Пример доступа к результатам после выполнения пайплайна
    if runner and runner.board_storage.inspection_results:
        print("\nДоступ к результатам инспекции:")
        print("  runner.board_storage.inspection_results - словарь всех результатов")
        print("  runner.board_storage.etalon_components - словарь эталонных компонентов")
        print("  runner.board_storage.control_components - словарь контрольных компонентов")
        print("  runner.board_storage.aligned_control_images - словарь выровненных контрольных изображений")
