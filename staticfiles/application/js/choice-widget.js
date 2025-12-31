document.addEventListener('DOMContentLoaded', function() {
    // Для всех виджетов выбора
    document.querySelectorAll('.choice-select').forEach(select => {
        const container = select.closest('.form-row');
        const textInput = container.querySelector('.custom-input');
        
        // Показываем/скрываем поле ввода
        function toggleInput() {
            if (select.value === 'other') {
                textInput.style.display = 'block';
                textInput.required = true;
            } else {
                textInput.style.display = 'none';
                textInput.required = false;
            }
        }
        
        // Инициализация
        toggleInput();
        
        // Обработчик изменений
        select.addEventListener('change', toggleInput);
    });
});