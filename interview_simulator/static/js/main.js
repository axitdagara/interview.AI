document.addEventListener("DOMContentLoaded", () => {
    const nav = document.querySelector(".site-nav");
    const revealItems = Array.from(document.querySelectorAll(".reveal"));

    const syncNavShadow = () => {
        if (!nav) {
            return;
        }
        nav.classList.toggle("is-scrolled", window.scrollY > 8);
    };

    syncNavShadow();
    window.addEventListener("scroll", syncNavShadow, { passive: true });

    revealItems.forEach((item, index) => {
        const delay = Math.min(index * 0.06, 0.36);
        item.style.setProperty("--delay", `${delay}s`);
    });

    if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("is-visible");
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.14 }
        );

        revealItems.forEach((item) => observer.observe(item));
    } else {
        revealItems.forEach((item) => item.classList.add("is-visible"));
    }

    const timerRange = document.getElementById("timerRange");
    const timerValue = document.getElementById("timerValue");
    if (timerRange && timerValue) {
        const updateTimerText = () => {
            timerValue.textContent = `${timerRange.value} sec`;
        };
        timerRange.addEventListener("input", updateTimerText);
        updateTimerText();
    }
});
