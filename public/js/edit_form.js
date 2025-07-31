document.addEventListener('DOMContentLoaded', function() {
    
    // ===============================================
    // KALKULASI OTOMATIS UNTUK MODUL SP2D (DURASI SP2D)
    // ===============================================
    const timeSlotGroups = document.querySelectorAll('.time-slot-group');
    if (timeSlotGroups.length > 0) {
        const updateAggregateTotals = () => {
            let aggregateTotal = 0;
            let aggregateLt1 = 0;

            const allSlotTotals = document.querySelectorAll('.time-slot-group input[name*="-"]:not([name*="<"]):not([name*=">"])');
            allSlotTotals.forEach(input => {
                aggregateTotal += parseInt(input.value) || 0;
            });

            const allSlotLt1s = document.querySelectorAll('.time-slot-group input[name*="< 1 Jam"]');
            allSlotLt1s.forEach(input => {
                aggregateLt1 += parseInt(input.value) || 0;
            });

            const aggregateTotalInput = document.querySelector('.form-actions-aggregate input[name="Total"]');
            const aggregateLt1Input = document.querySelector('.form-actions-aggregate input[name="< 1 Jam"]');

            if (aggregateTotalInput) aggregateTotalInput.value = aggregateTotal;
            if (aggregateLt1Input) aggregateLt1Input.value = aggregateLt1;
        };

        timeSlotGroups.forEach(group => {
            const totalInput = group.querySelector('input[name*="' + group.querySelector('h4').textContent.trim() + '"]:not([name*="<"]):not([name*=">"])');
            const lt1Input = group.querySelector('input[name*="< 1 Jam"]');
            const gt1Input = group.querySelector('input[name*="> 1 Jam"]');

            if (!totalInput || !lt1Input || !gt1Input) return;

            const updateTotal = () => {
                const lt1Value = parseInt(lt1Input.value) || 0;
                const gt1Value = parseInt(gt1Input.value) || 0;
                totalInput.value = lt1Value + gt1Value;
                updateAggregateTotals();
            };

            lt1Input.addEventListener('input', updateTotal);
            gt1Input.addEventListener('input', updateTotal);
        });

        updateAggregateTotals(); // Panggil saat awal
    }

    // ================================================================
    // FUNGSI KALKULASI GENERIK UNTUK MODUL ADK, PMRT, DAN KARWAS
    // ================================================================
    const setupAutoCalculation = (totalFieldId, componentFieldIds) => {
        const totalField = document.getElementById(totalFieldId);
        const componentFields = componentFieldIds.map(id => document.getElementById(id));

        if (!totalField || componentFields.some(field => field === null)) {
            return;
        }

        const calculateTotal = () => {
            let sum = 0;
            componentFields.forEach(field => {
                sum += parseInt(field.value) || 0;
            });
            totalField.value = sum;
        };

        componentFields.forEach(field => {
            field.addEventListener('input', calculateTotal);
        });
        
        calculateTotal();
    };

    // Terapkan fungsi kalkulasi untuk setiap modul
    setupAutoCalculation('total-adk-kontraktual', ['adk-tepat-waktu', 'adk-terlambat']);
    setupAutoCalculation('total-pmrt', ['pmrt-formal', 'pmrt-substantif']);
    setupAutoCalculation('total-up', ['karwas-up-1-2', 'karwas-up-gt-2']);
    setupAutoCalculation('total-tup', ['karwas-tup-1-2', 'karwas-tup-gt-2']);

    // ================================================================
    // KODE BARU: MENGAKTIFKAN DATE PICKER (FLATPICKR)
    // ================================================================
    flatpickr(".datepicker", {
        dateFormat: "d-M-Y", // Format: 31-Jul-2023 (sesuai format sheet)
        locale: "id"         // Gunakan Bahasa Indonesia
    });

});