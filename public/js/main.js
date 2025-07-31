// static/js/main.js
document.addEventListener('DOMContentLoaded', function() {
    // --- LOGIKA UNTUK SIDEBAR (TIDAK BERUBAH) ---
    const sidebar = document.getElementById('sidebar');
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const closeSidebarBtn = document.getElementById('close-sidebar-btn');
    const mobileOverlay = document.getElementById('mobile-overlay');

    const openSidebar = () => {
        if(sidebar && mobileOverlay) {
            sidebar.classList.remove('-translate-x-full');
            mobileOverlay.classList.remove('hidden');
        }
    };

    const closeSidebar = () => {
        if(sidebar && mobileOverlay) {
            sidebar.classList.add('-translate-x-full');
            mobileOverlay.classList.add('hidden');
        }
    };
    
    if(mobileMenuBtn) mobileMenuBtn.addEventListener('click', openSidebar);
    if(closeSidebarBtn) closeSidebarBtn.addEventListener('click', closeSidebar);
    if(mobileOverlay) mobileOverlay.addEventListener('click', closeSidebar);

    // ======================================================
    // LOGIKA BARU YANG DIPERBAIKI UNTUK ACCORDION MENU KPPN
    // ======================================================
    const accordionLinks = document.querySelectorAll('a.has-submenu');

    accordionLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const submenu = this.nextElementSibling;
            const arrow = this.querySelector('.arrow');
            const isActive = this.classList.contains('bg-blue-600'); // Cek apakah sudah aktif

            // Hapus status aktif dari semua link KPPN lain
            accordionLinks.forEach(otherLink => {
                if (otherLink !== this) {
                    otherLink.classList.remove('bg-blue-600', 'text-white', 'font-semibold');
                    otherLink.classList.add('text-gray-600', 'hover:bg-blue-100', 'hover:text-gray-800');
                    otherLink.nextElementSibling.classList.add('hidden');
                    otherLink.querySelector('.arrow').classList.remove('rotate-90', 'text-white');
                }
            });
            
            // Toggle menu yang diklik
            if (isActive) {
                // Jika sudah aktif, tutup menu
                submenu.classList.add('hidden');
                arrow.classList.remove('rotate-90', 'text-white');
                this.classList.remove('bg-blue-600', 'text-white', 'font-semibold');
                this.classList.add('text-gray-600', 'hover:bg-blue-100', 'hover:text-gray-800');
            } else {
                // Jika tidak aktif, buka menu
                submenu.classList.remove('hidden');
                arrow.classList.add('rotate-90', 'text-white');
                this.classList.add('bg-blue-600', 'text-white', 'font-semibold');
                this.classList.remove('text-gray-600', 'hover:bg-blue-100', 'hover:text-gray-800');
            }
        });
    });

    // --- LOGIKA BARU UNTUK MEMUAT DATA DASBOR DENGAN TAMPILAN TAILWIND CSS ---
    const dashboardModul = document.querySelector('.dashboard-modul');
    if (dashboardModul) {
        const kppnId = dashboardModul.dataset.kppnId;
        const modulId = dashboardModul.dataset.modulId;
        const tahunSelect = document.getElementById('filter-tahun');
        const bulanSelect = document.getElementById('filter-bulan');
        const reportsContainer = document.getElementById('reports-container');
        const summaryContainer = document.getElementById('monthly-summary-container');
        
        // Atur filter ke tanggal saat ini
        const today = new Date();
        tahunSelect.value = today.getFullYear();
        bulanSelect.value = today.toLocaleString('id-ID', { month: 'long' });

        let activeCharts = [];
        Chart.register(ChartDataLabels);

        // Opsi default untuk label data pada chart
        const defaultDatalabelsOptions = { color: '#FFFFFF', anchor: 'center', align: 'center', font: { weight: 'bold' }, formatter: (value) => (value > 0 ? value : null) };
        const topDatalabelsOptions = { color: '#333', anchor: 'end', align: 'end', font: { weight: 'bold' }, offset: -5, formatter: (value) => (value > 0 ? value : null) };

        // === FUNGSI RENDER TAMPILAN BARU ===

        /**
         * Render Komponen Modul SP2D
         */
        function renderSP2DComponent(data, targetElement, title, chartId) {
            let tableHTML = '';
            data.table_rows.forEach(row => { 
                tableHTML += `<tr class="border-b hover:bg-gray-50">
                                <td class="p-3 font-medium text-gray-700">${row.jam_upload}</td>
                                <td class="p-3 text-center">${row.total}</td>
                                <td class="p-3 text-center text-green-600 font-semibold">${row.kurang_1_jam}</td>
                                <td class="p-3 text-center font-bold text-blue-600">${row.persen}</td>
                              </tr>`; 
            });

            const contentHTML = `
                <div class="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
                    <div class="p-5 bg-gray-50 border-b">
                        <h4 class="text-xl font-bold text-gray-800">${title}</h4>
                        <p class="text-sm text-gray-500">${data.period}</p>
                    </div>
                    <div class="p-5 grid grid-cols-1 md:grid-cols-5 gap-6 items-center">
                        <div class="md:col-span-2">
                            <table class="w-full text-sm text-left text-gray-600">
                                <thead class="text-xs text-gray-700 uppercase bg-gray-100">
                                    <tr>
                                        <th class="p-3">Jam Upload</th>
                                        <th class="p-3 text-center">Total</th>
                                        <th class="p-3 text-center">&lt; 1 Jam</th>
                                        <th class="p-3 text-center">%</th>
                                    </tr>
                                </thead>
                                <tbody>${tableHTML}</tbody>
                            </table>
                        </div>
                        <div class="md:col-span-3 h-80">
                            <canvas id="${chartId}"></canvas>
                        </div>
                    </div>
                </div>`;

            targetElement.innerHTML = contentHTML;
            const ctx = document.getElementById(chartId).getContext('2d');
            const newChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.chart_data.labels,
                    datasets: [
                        { label: '%', data: data.chart_data.percentage, type: 'line', borderColor: '#16a34a', backgroundColor: '#16a34a', yAxisID: 'y-axis-percent', order: 1, datalabels: { display: false } },
                        { label: 'Total', data: data.chart_data.totals, backgroundColor: 'rgba(59, 130, 246, 0.7)', yAxisID: 'y-axis-count', order: 2, datalabels: topDatalabelsOptions },
                        { label: '< 1 Jam', data: data.chart_data.less_than_1_hour, backgroundColor: 'rgba(251, 191, 36, 0.8)', yAxisID: 'y-axis-count', order: 3, datalabels: topDatalabelsOptions }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } }, scales: { 'y-axis-count': { position: 'left', beginAtZero: true, title: { display: true, text: 'Jumlah SP2D' } }, 'y-axis-percent': { position: 'right', min: 0, max: 100, grid: { drawOnChartArea: false }, ticks: { callback: v => v + '%' }, title: { display: true, text: 'Persentase' } } } }
            });
            activeCharts.push(newChart);
        }

        /**
         * Render Komponen KPI (Untuk ADK, PMRT, Karwas)
         */
        function renderKPIComponent(data, monthlyChartData, targetElement, config) {
            const card = document.createElement('div');
            card.className = 'bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden';
            
            const kpiBoxes = config.kpis(data.kpi).map(k => `
                <div class="bg-gray-50 p-4 rounded-lg text-center border">
                    <div class="text-sm text-gray-500">${k.label}</div>
                    <div class="text-3xl font-extrabold text-blue-600">${k.value}</div>
                </div>
            `).join('');

            card.innerHTML = `
                <div class="p-5 bg-gray-50 border-b">
                    <h4 class="text-xl font-bold text-gray-800">${config.title}</h4>
                    <p class="text-sm text-gray-500">${data.period}</p>
                </div>
                <div class="p-5 grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
                    <div class="space-y-4">
                        <div class="grid grid-cols-2 gap-4">${kpiBoxes}</div>
                    </div>
                    <div class="h-80">
                        <canvas id="${config.chartId}"></canvas>
                    </div>
                </div>
            `;
            targetElement.appendChild(card);
            
            const ctx = document.getElementById(config.chartId).getContext('2d');
            let chartConfig;

            // Jika ada data chart bulanan, gunakan itu. Jika tidak, buat chart mingguan.
            if (monthlyChartData && monthlyChartData.Bulan && monthlyChartData.Bulan.length > 0) {
                chartConfig = config.monthlyChart(monthlyChartData);
            } else {
                chartConfig = config.weeklyChart(data.kpi);
            }

            const newChart = new Chart(ctx, chartConfig);
            activeCharts.push(newChart);
        }

        /**
         * Render Komponen Modul Lainnya
         */
        function renderLainnyaComponent(data, monthlyChartData, targetElement, title, chartId) {
            const kpi = data.kpi;
            const isMonthlySummary = title.toLowerCase().includes('akumulasi');
            let bankContentHTML = '';

            // Hapus chart yang mungkin sudah ada sebelumnya untuk menghindari duplikasi
            const existingChart = Chart.getChart(`${chartId}-bank`);
            if (existingChart) {
                existingChart.destroy();
            }

            if (isMonthlySummary && monthlyChartData && monthlyChartData.labels) {
                // TAMPILAN KHUSUS UNTUK LAPORAN AKUMULASI DENGAN GRAFIK KINERJA RETUR BARU
                bankContentHTML = `
                    <div class="h-96"><canvas id="${chartId}-bank"></canvas></div>
                `;

                setTimeout(() => {
                    const canvasElement = document.getElementById(`${chartId}-bank`);
                    if (canvasElement) {
                        const tepatWaktu = kpi.bank.tepat_waktu_retur || 0;
                        const total = kpi.bank.total_retur || 0;
                        const terlambat = total > 0 ? total - tepatWaktu : 0;
                        const persentase = total > 0 ? (tepatWaktu / total) * 100 : 0;

                        const newChart = new Chart(canvasElement.getContext('2d'), {
                            type: 'bar',
                            data: {
                                labels: ['Kinerja Retur'],
                                datasets: [{
                                    label: 'Retur Tepat Waktu (<=8 Hari)',
                                    data: [tepatWaktu], // Menggunakan variabel yang sudah dihitung
                                    backgroundColor: 'rgba(59, 130, 246, 0.7)',
                                    yAxisID: 'y-jumlah',
                                    datalabels: { // Tambahkan atau modifikasi objek datalabels
                                        color: 'black', // Tambahkan warna putih
                                        anchor: 'center',
                                        align: 'center',
                                        font: { weight: 'bold' },
                                        formatter: (value) => value
                                    }
                                }, {
                                    label: 'Retur Terlambat (>8 Hari)',
                                    data: [terlambat], // Menggunakan variabel yang sudah dihitung
                                    backgroundColor: 'rgba(239, 68, 68, 0.7)',
                                    yAxisID: 'y-jumlah',
                                    datalabels: { // Tambahkan atau modifikasi objek datalabels
                                        color: 'black', // Tambahkan warna putih
                                        anchor: 'center',
                                        align: 'center',
                                        font: { weight: 'bold' },
                                        formatter: (value) => value
                                    }
                                }, {
                                    label: '% Tepat Waktu',
                                    data: [persentase], // Menggunakan variabel yang sudah dihitung
                                    type: 'line',
                                    borderColor: 'rgba(22, 163, 74, 1)',
                                    backgroundColor: 'rgba(22, 163, 74, 1)',
                                    yAxisID: 'y-persen',
                                    tension: 0.1,
                                    datalabels: {
                                        display: true,
                                        anchor: 'end',
                                        align: 'top',
                                        color: '#000000ff',
                                        font: { weight: 'bold' },
                                        formatter: (value) => value.toFixed(2) + '%'
                                    }
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: { legend: { position: 'top' } },
                                scales: {
                                    'y-jumlah': { type: 'linear', position: 'left', title: { display: true, text: 'Jumlah' } },
                                    'y-persen': { type: 'linear', position: 'right', min: 0, max: 100, grid: { drawOnChartArea: false }, ticks: { callback: (value) => value + '%' }, title: { display: true, text: 'Persentase' } }
                                }
                            }
                        });
                        activeCharts.push(newChart);
                    }
                }, 0);

            } else {
                // TAMPILAN MINGGUAN DENGAN GRAFIK DONAT (tetap sama)
                bankContentHTML = `<div class="h-64"><canvas id="${chartId}-bank"></canvas></div>`;
                setTimeout(() => {
                    const canvasElement = document.getElementById(`${chartId}-bank`);
                    if (canvasElement) {
                        const tepatWaktuRetur = kpi.bank.tepat_waktu_retur || 0;
                        const totalRetur = kpi.bank.total_retur || 0;
                        const terlambatRetur = totalRetur > 0 ? totalRetur - tepatWaktuRetur : 0;
                        const chartData = {
                            type: 'doughnut',
                            data: { labels: ['Tepat Waktu (<=8 Hari)', 'Terlambat (>8 Hari)'], datasets: [{ data: [tepatWaktuRetur, terlambatRetur], backgroundColor: ['#22c55e', '#ef4444ff'], borderColor: '#fff' }] },
                            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' }, datalabels: defaultDatalabelsOptions } }
                        };
                        activeCharts.push(new Chart(canvasElement.getContext('2d'), chartData));
                    }
                }, 0);
            }
            
            // STRUKTUR HTML UTAMA YANG MENGGABUNGKAN SEMUA MODUL
            const contentHTML = `
                <div class="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                    <div class="p-5 bg-gray-50 dark:bg-gray-700/50 border-b dark:border-gray-600">
                        <h4 class="text-xl font-bold text-gray-800 dark:text-gray-100">${title}</h4>
                        <p class="text-sm text-gray-500 dark:text-gray-400">${data.period}</p>
                    </div>
                    <div class="p-5 space-y-8">
                        <div>
                            <h5 class="font-bold text-lg text-gray-700 dark:text-gray-200 mb-3">Modul Penerimaan</h5>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div class="bg-blue-50 dark:bg-gray-700 p-4 rounded-lg border dark:border-gray-600"><div class="text-gray-600 dark:text-gray-300">PFK Salah Satker/Akun</div><div class="text-2xl font-bold text-blue-800 dark:text-blue-300">${kpi.penerimaan.salah_satker_akun}</div></div>
                                <div class="bg-blue-50 dark:bg-gray-700 p-4 rounded-lg border dark:border-gray-600"><div class="text-gray-600 dark:text-gray-300">PFK Salah Potong</div><div class="text-2xl font-bold text-blue-800 dark:text-blue-300">${kpi.penerimaan.salah_potong}</div></div>
                                <div class="bg-blue-50 dark:bg-gray-700 p-4 rounded-lg border dark:border-gray-600"><div class="text-gray-600 dark:text-gray-300">PFK Salah Pecahan</div><div class="text-2xl font-bold text-blue-800 dark:text-blue-300">${kpi.penerimaan.salah_pecahan}</div></div>
                            </div>
                        </div>

                        <div>
                            <h5 class="font-bold text-lg text-gray-700 dark:text-gray-200 mb-3">Data Suspend</h5>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div class="bg-yellow-50 dark:bg-gray-700 p-4 rounded-lg border dark:border-gray-600"><div class="text-gray-600 dark:text-gray-300">Pengembalian Belanja</div><div class="text-2xl font-bold text-yellow-800 dark:text-yellow-300">${kpi.suspend.pengembalian_belanja}</div></div>
                                <div class="bg-yellow-50 dark:bg-gray-700 p-4 rounded-lg border dark:border-gray-600"><div class="text-gray-600 dark:text-gray-300">Satker Belum Koreksi</div><div class="text-2xl font-bold text-yellow-800 dark:text-yellow-300">${kpi.suspend.satker_belum_koreksi}</div></div>
                                <div class="bg-yellow-50 dark:bg-gray-700 p-4 rounded-lg border dark:border-gray-600"><div class="text-gray-600 dark:text-gray-300">Akun Belum Koreksi</div><div class="text-2xl font-bold text-yellow-800 dark:text-yellow-300">${kpi.suspend.akun_belum_koreksi}</div></div>
                            </div>
                        </div>

                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                            <div>
                                <h5 class="font-bold text-lg text-gray-700 dark:text-gray-200 mb-3">Modul Bank</h5>
                                <div class="space-y-4">
                                    <div class="grid grid-cols-2 gap-4">
                                        <div class="bg-purple-50 dark:bg-gray-700 p-4 rounded-lg border dark:border-gray-600"><div class="text-gray-600 dark:text-gray-300">SP2D Void</div><div class="text-2xl font-bold text-purple-800 dark:text-purple-300">${kpi.bank.sp2d_void}</div></div>
                                        <div class="bg-purple-50 dark:bg-gray-700 p-4 rounded-lg border dark:border-gray-600"><div class="text-gray-600 dark:text-gray-300">SP2D Backdate</div><div class="text-2xl font-bold text-purple-800 dark:text-purple-300">${kpi.bank.sp2d_backdate}</div></div>
                                    </div>
                                    ${bankContentHTML}
                                </div>
                            </div>
                            <div>
                                <h5 class="font-bold text-lg text-gray-700 dark:text-gray-200 mb-3">Modul Renkas & SBSN</h5>
                                <div class="space-y-4">
                                    <div class="bg-green-50 dark:bg-gray-700 p-4 rounded-lg border dark:border-gray-600"><div class="text-gray-600 dark:text-gray-300">Deviasi RPD Harian</div><div class="text-2xl font-bold text-green-800 dark:text-green-300">${kpi.renkas.deviasi_rpd_harian}</div></div>
                                    <div class="bg-green-50 dark:bg-gray-700 p-4 rounded-lg border dark:border-gray-600"><div class="text-gray-600 dark:text-gray-300">Dispensasi SPM Tanpa RPD</div><div class="text-2xl font-bold text-green-800 dark:text-green-300">${kpi.renkas.dispensasi_spm}</div></div>
                                    <div class="bg-indigo-50 dark:bg-gray-700 p-4 rounded-lg border dark:border-gray-600"><div class="text-gray-600 dark:text-gray-300">Deviasi RPD SBSN</div><div class="text-2xl font-bold text-indigo-800 dark:text-indigo-300">${kpi.sbsn.deviasi_rpd_sbsn}</div></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            targetElement.innerHTML = contentHTML;
        }

        // --- Konfigurasi untuk setiap Modul KPI ---
        const kpiConfigs = {
            'adk': {
                title: 'Laporan ADK Kontraktual',
                kpis: (kpi) => [
                    { label: 'Tepat Waktu', value: kpi.tepat_waktu || 0 },
                    { label: 'Terlambat', value: kpi.terlambat || 0 }
                ],
                weeklyChart: (kpi) => ({
                    type: 'doughnut',
                    data: { 
                        labels: ['Tepat Waktu', 'Terlambat'], 
                        datasets: [{ 
                            data: [kpi.tepat_waktu, kpi.terlambat], 
                            backgroundColor: ['#2563eb', '#f59e0b'], 
                            borderColor: '#fff',
                            borderWidth: 2
                        }] 
                    },
                    options: { 
                        responsive: true, 
                        maintainAspectRatio: false, 
                        plugins: { 
                            legend: { position: 'top' }, 
                            // PERBAIKAN: Menambahkan formatter untuk persentase
                            datalabels: {
                                color: '#fff',
                                font: { weight: 'bold' },
                                formatter: (value, context) => {
                                    const total = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                                    const percentage = total > 0 ? (value / total * 100) : 0;
                                    return percentage.toFixed(1) + '%';
                                }
                            }
                        } 
                    }
                }),
                monthlyChart: (chartData) => ({
                    type: 'bar',
                    data: { labels: chartData.Bulan, datasets: [
                        { label: '%', type: 'line', data: chartData['%'], borderColor: '#16a34a', yAxisID: 'y-percent' },
                        { label: '< 5 Hari', data: chartData['<5 hari'], backgroundColor: 'rgba(59, 130, 246, 0.7)', yAxisID: 'y-count' },
                        { label: 'Total', data: chartData.Total, backgroundColor: 'rgba(107, 114, 128, 0.5)', yAxisID: 'y-count' }
                    ]},
                    options: { responsive: true, maintainAspectRatio: false, scales: { 'y-count': { position: 'left', title: { text: 'Jumlah', display: true } }, 'y-percent': { position: 'right', grid: { drawOnChartArea: false }, title: { text: '%', display: true } } } }
                })
            },
            'pmrt': {
                title: 'Laporan Penolakan PMRT',
                kpis: (kpi) => [
                    { label: 'Penolakan Formal', value: kpi.formal || 0 },
                    { label: 'Penolakan Substantif', value: kpi.substantif || 0 }
                ],
                weeklyChart: (kpi) => ({
                    type: 'doughnut', // <-- UBAH TIPE GRAFIK
                    data: { 
                        labels: ['Penolakan Formal', 'Penolakan Substantif'], 
                        datasets: [{ 
                            data: [kpi.formal, kpi.substantif], 
                            backgroundColor: ['#3b82f6', '#f97316'], // Biru dan Oranye
                            borderColor: '#fff',
                            borderWidth: 2
                        }] 
                    },
                    options: { 
                        responsive: true, 
                        maintainAspectRatio: false, 
                        plugins: { 
                            legend: { position: 'top' }, 
                            // TAMBAHKAN FORMATTER PERSENTASE
                            datalabels: {
                                color: '#fff',
                                font: { weight: 'bold' },
                                formatter: (value, context) => {
                                    const total = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                                    const percentage = total > 0 ? (value / total * 100) : 0;
                                    if (percentage < 5) return '';
                                    return percentage.toFixed(1) + '%';
                                }
                            }
                        } 
                    }
                }),
                monthlyChart: (chartData) => ({
                    type: 'bar',
                    data: { labels: chartData.Bulan, datasets: [{ label: 'Formal', data: chartData.Formal, backgroundColor: '#3b82f6' }, { label: 'Substantif', data: chartData.Substantif, backgroundColor: '#f97316' }] },
                    options: { responsive: true, maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true } } }
                })
            },
            'karwas': {
                title: 'Laporan Karwas UP/TUP',
                kpis: (kpi) => [
                    { label: 'Total Pengawasan UP', value: kpi.up.total || 0 },
                    { label: 'Total Pengawasan TUP', value: kpi.tup.total || 0 }
                ],
                weeklyChart: (kpi) => ({
                    type: 'bar',
                    data: { labels: ['UP Jatuh Tempo', 'TUP Terlambat'], datasets: [
                        { label: '1-2 Hari', data: [kpi.up.jatuh_tempo_1_2, kpi.tup.terlambat_1_2], backgroundColor: '#3b82f6'}, 
                        { label: '>2 Hari', data: [kpi.up.jatuh_tempo_gt_2, kpi.tup.terlambat_gt_2], backgroundColor: '#ef4444' }
                    ]},
                    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } }, scales: { x: { stacked: false }, y: { stacked: false, beginAtZero: true, title: { display: true, text: 'Jumlah' } } } }
                }),
                monthlyChart: (chartData) => ({ /* Placeholder jika ada data bulanan */ type: 'bar', data: { labels:[], datasets:[] }})
            }
        };


        /**
         * Fungsi Utama untuk Memuat dan Merender Dashboard
         */
        async function updateDashboard() {
            // Hancurkan chart lama dan bersihkan kontainer
            activeCharts.forEach(chart => chart.destroy());
            activeCharts = [];
            reportsContainer.innerHTML = '<p class="text-center text-gray-500 py-10">Memuat laporan...</p>';
            summaryContainer.innerHTML = '';

            const tahun = tahunSelect.value;
            const bulan = bulanSelect.value;
            const API_URL = `/api/data/${kppnId}/${modulId}?tahun=${tahun}&bulan=${bulan}`;

            const exportBtn = document.getElementById('export-excel-btn');
            if (exportBtn) {
                const exportUrl = `/export/excel/${kppnId}/${modulId}?tahun=${tahun}&bulan=${bulan}`;
                exportBtn.href = exportUrl;
            }

            try {
                const response = await fetch(API_URL);
                const data = await response.json();

                if (!response.ok || data.error) throw new Error(data.error || 'Gagal mengambil data');
                
                reportsContainer.innerHTML = ''; // Kosongkan setelah berhasil fetch

                // Render Summary Bulanan
                if (data.monthly_summary) {
                    if (modulId === 'sp2d') {
                        renderSP2DComponent(data.monthly_summary, summaryContainer, 'Laporan Akumulasi Bulanan', 'chart-m-summary');
                    } else if (kpiConfigs[modulId]) {
                        const config = { ...kpiConfigs[modulId], chartId: 'chart-m-summary' };
                        // Buat elemen div untuk summary karena renderKPIComponent butuh elemen child
                        const summaryDiv = document.createElement('div');
                        summaryContainer.appendChild(summaryDiv);
                        renderKPIComponent(data.monthly_summary, data.chart_data, summaryDiv, config);
                    } else if (modulId === 'lainnya') {
                        renderLainnyaComponent(data.monthly_summary, data.chart_data, summaryContainer, 'Laporan Akumulasi Bulanan', 'chart-m-summary');
                    }
                }

                // Render Laporan Mingguan
                if (data.weekly_reports && data.weekly_reports.length > 0) {
                    data.weekly_reports.forEach((report, index) => {
                        const reportElement = document.createElement('div');
                        reportsContainer.appendChild(reportElement);

                        if (modulId === 'sp2d') {
                            renderSP2DComponent(report, reportElement, `Laporan Mingguan #${index + 1}`, `chart-w-${index}`);
                        } else if (kpiConfigs[modulId]) {
                            const config = { ...kpiConfigs[modulId], chartId: `chart-w-${index}` };
                             renderKPIComponent(report, null, reportElement, config);
                        } else if (modulId === 'lainnya') {
                            renderLainnyaComponent(report, null, reportElement, `Laporan Mingguan #${index + 1}`, `chart-w-${index}`);
                        }
                    });
                } else {
                    reportsContainer.innerHTML = '<p class="text-center text-gray-500 py-10 bg-white rounded-lg shadow">Tidak ada laporan mingguan untuk periode ini.</p>';
                }

            } catch (error) {
                console.error("Fetch error:", error);
                reportsContainer.innerHTML = `<div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg" role="alert"><strong class="font-bold">Error:</strong><span class="block sm:inline"> ${error.message}</span></div>`;
            }
        }

        // Event listener dan pemanggilan awal
        tahunSelect.addEventListener('change', updateDashboard);
        bulanSelect.addEventListener('change', updateDashboard);
        updateDashboard();
    }
});