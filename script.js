document.addEventListener('DOMContentLoaded', () => {
  addOperationRow();

  document.getElementById('add-operation').addEventListener('click', addOperationRow);
  document.getElementById('download').addEventListener('click', downloadPdf);
});

function addOperationRow() {
  const tbody = document.querySelector('#operations-table tbody');
  const row = document.createElement('tr');
  row.innerHTML = `
    <td><input type="date" class="op-date" required></td>
    <td><input type="text" class="op-desc" required></td>
    <td><input type="number" step="0.01" class="op-amount" required></td>
    <td><button type="button" class="remove">✕</button></td>
  `;
  row.querySelector('.remove').addEventListener('click', () => row.remove());
  tbody.appendChild(row);
}

function downloadPdf() {
  const fio = document.getElementById('fio').value.trim();
  const account = document.getElementById('account').value.trim();
  const start = document.getElementById('start-date').value;
  const end = document.getElementById('end-date').value;

  const operations = Array.from(document.querySelectorAll('#operations-table tbody tr')).map(row => ({
    date: row.querySelector('.op-date').value,
    desc: row.querySelector('.op-desc').value,
    amount: row.querySelector('.op-amount').value
  })).filter(op => op.date || op.desc || op.amount);

  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();
  let y = 15;
  doc.setFontSize(16);
  doc.text('Выписка по счёту', 14, y);
  y += 10;
  doc.setFontSize(12);
  doc.text(`ФИО: ${fio}`, 14, y);
  y += 6;
  doc.text(`Счёт: ${account}`, 14, y);
  y += 6;
  doc.text(`Период: ${start} — ${end}`, 14, y);
  y += 10;

  const rows = operations.map(op => [op.date, op.desc, op.amount]);
  doc.autoTable({
    head: [['Дата', 'Описание', 'Сумма']],
    body: rows,
    startY: y
  });

  const finalY = doc.lastAutoTable ? doc.lastAutoTable.finalY : y;
  const total = operations.reduce((sum, op) => sum + parseFloat(op.amount || 0), 0);
  doc.text(`Итого: ${total.toFixed(2)}`, 14, finalY + 10);

  doc.save('statement.pdf');
}
