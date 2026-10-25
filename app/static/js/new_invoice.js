
document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("invoice-form");
    const lines = document.getElementById("invoice-lines");
    const addButton = document.getElementById("add-product-btn");

    if (!form || !lines || !addButton) return;

    const money = (value) => {
        return new Intl.NumberFormat("vi-VN", {
            style: "currency",
            currency: "VND",
            maximumFractionDigits: 2
        }).format(value);
    };

    function updateTotals() {
        let total = 0;
        let totalQuantity = 0;
        let itemCount = 0;

        lines.querySelectorAll(".invoice-line").forEach(row => {
            const select = row.querySelector(".invoice-product-select");
            const quantityInput = row.querySelector(".invoice-quantity");
            const option = select.selectedOptions[0];

            const price = Number(option?.dataset.price || 0);
            const quantity = Number(quantityInput.value || 0);

            const validQuantity = Number.isInteger(quantity)
                && quantity >= 1 && quantity <= 100000;

            const lineTotal = validQuantity ? price * quantity : 0;

            row.querySelector(".invoice-unit-price").textContent = money(price);
            row.querySelector(".invoice-line-total").textContent = money(lineTotal);

            total += lineTotal;

            if (validQuantity && select.value) {
                totalQuantity += quantity;
                itemCount++;
            }
        });

        document.getElementById("invoice-item-count").textContent = itemCount;
        document.getElementById("invoice-quantity-count").textContent = totalQuantity;
        document.getElementById("invoice-grand-total").textContent = money(total);
    }

    addButton.addEventListener("click", function () {
        const firstRow = lines.querySelector(".invoice-line");

        if (!firstRow) return;

        const newRow = firstRow.cloneNode(true);

        newRow.querySelector(".invoice-quantity").value = "1";
        newRow.querySelector(".invoice-product-select").selectedIndex = 0;

        lines.appendChild(newRow);
        updateTotals();
    });

    lines.addEventListener("change", updateTotals);
    lines.addEventListener("input", updateTotals);

    lines.addEventListener("click", function (event) {
        const removeButton = event.target.closest(".invoice-remove-btn");

        if (!removeButton) return;

        const rows = lines.querySelectorAll(".invoice-line");

        if (rows.length <= 1) {
            alert("Hóa đơn phải có ít nhất một dòng sản phẩm.");
            return;
        }

        removeButton.closest(".invoice-line").remove();
        updateTotals();
    });

    form.addEventListener("submit", function (event) {
        const rows = lines.querySelectorAll(".invoice-line");

        if (rows.length === 0) {
            event.preventDefault();
            alert("Vui lòng thêm ít nhất một sản phẩm.");
            return;
        }

        for (const row of rows) {
            const quantity = Number(
                row.querySelector(".invoice-quantity").value
            );

            if (!Number.isInteger(quantity)
                || quantity < 1
                || quantity > 100000) {
                event.preventDefault();
                alert("Số lượng phải là số nguyên từ 1 đến 100000.");
                return;
            }
        }
    });

    updateTotals();
});
