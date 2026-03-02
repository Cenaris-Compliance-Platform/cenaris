(function () {
  function renderLineChart(canvasId, labels, datasets) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return;
    new Chart(ctx, {
      type: 'line',
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          y: { beginAtZero: true },
        },
      },
    });
  }

  function renderBarChart(canvasId, labels, datasets) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return;
    new Chart(ctx, {
      type: 'bar',
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  function renderPieChart(canvasId, labels, values, colors) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return;
    new Chart(ctx, {
      type: 'pie',
      data: {
        labels: labels,
        datasets: [{ data: values, backgroundColor: colors }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
      },
    });
  }

  window.renderLineChart = renderLineChart;
  window.renderBarChart = renderBarChart;
  window.renderPieChart = renderPieChart;

  var payload = window.analyticsPayload || {};
  var trends = payload.trends || {};
  var summary = payload.summary || {};
  var framework = payload.framework_analytics || [];
  var status = payload.status_distribution || {};
  var uploadTypes = (payload.uploads || {}).content_type_distribution || {};

  renderLineChart('complianceTrendChart', trends.labels || [], [
    {
      label: 'Compliance %',
      data: trends.compliance_percent || [],
      borderColor: '#0d6efd',
      backgroundColor: 'rgba(13,110,253,0.15)',
      fill: true,
      tension: 0.35,
    },
    {
      label: 'Compliant updates',
      data: trends.compliant_updates || [],
      borderColor: '#198754',
      backgroundColor: 'rgba(25,135,84,0.10)',
      fill: false,
      tension: 0.35,
    },
  ]);

  renderBarChart(
    'frameworkBarChart',
    framework.map(function (item) { return item.framework; }),
    [{
      label: 'Compliance %',
      data: framework.map(function (item) { return item.compliance_rate; }),
      backgroundColor: '#0dcaf0',
    }]
  );

  renderLineChart('uploadLineChart', trends.labels || [], [
    {
      label: 'Uploads',
      data: trends.uploads || [],
      borderColor: '#6f42c1',
      backgroundColor: 'rgba(111,66,193,0.15)',
      fill: true,
      tension: 0.35,
    },
  ]);

  renderLineChart('activityLineChart', trends.labels || [], [
    {
      label: 'Login success',
      data: trends.login_success || [],
      borderColor: '#198754',
      backgroundColor: 'rgba(25,135,84,0.10)',
      fill: false,
      tension: 0.35,
    },
    {
      label: 'Login failure',
      data: trends.login_failure || [],
      borderColor: '#dc3545',
      backgroundColor: 'rgba(220,53,69,0.10)',
      fill: false,
      tension: 0.35,
    },
  ]);

  renderPieChart(
    'statusPieChart',
    Object.keys(status),
    Object.values(status),
    ['#dc3545', '#fd7e14', '#0d6efd', '#198754', '#6c757d']
  );

  renderPieChart(
    'uploadTypePieChart',
    Object.keys(uploadTypes),
    Object.values(uploadTypes),
    ['#0d6efd', '#198754', '#ffc107', '#dc3545', '#6f42c1', '#20c997', '#adb5bd']
  );
})();
