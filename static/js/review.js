const inputs = document.querySelectorAll(".review-input");

const ranges = {
    0: [1, 15],
    1: [16, 30],
    2: [31, 45],
    3: [46, 60],
    4: [61, 75]
};

inputs.forEach(input => {
    input.addEventListener("input", () => {
        const col = Number(input.dataset.col);
        const [min, max] = ranges[col];
        const value = Number(input.value);

        if (!value || value < min || value > max) {
            input.classList.add("input-suspicious");
        } else {
            input.classList.remove("input-suspicious");
        }
    });
});