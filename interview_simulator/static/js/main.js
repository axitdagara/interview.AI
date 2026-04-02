document.addEventListener("DOMContentLoaded", () => {
    const root = document.documentElement;
    const nav = document.querySelector(".site-nav");
    const navLinks = Array.from(document.querySelectorAll(".site-nav .nav-link"));
    const revealItems = Array.from(document.querySelectorAll(".reveal"));
    const themeToggle = document.getElementById("themeToggle");
    const themeToggleLabel = document.getElementById("themeToggleLabel");

    const applyTheme = (theme) => {
        const normalized = theme === "dark" ? "dark" : "light";
        root.setAttribute("data-theme", normalized);

        if (themeToggle) {
            const pressed = normalized === "dark";
            themeToggle.setAttribute("aria-pressed", String(pressed));
        }

        if (themeToggleLabel) {
            themeToggleLabel.textContent = normalized === "dark" ? "Light Mode" : "Dark Mode";
        }
    };

    const persistedTheme = localStorage.getItem("interview-ai-theme");
    const preferredTheme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";

    applyTheme(persistedTheme || preferredTheme);

    if (themeToggle) {
        themeToggle.addEventListener("click", () => {
            const current = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
            const next = current === "dark" ? "light" : "dark";
            applyTheme(next);
            localStorage.setItem("interview-ai-theme", next);

            if (document.getElementById("trendChart")) {
                window.setTimeout(() => window.location.reload(), 50);
            }
        });
    }

    const syncNavShadow = () => {
        if (!nav) {
            return;
        }
        nav.classList.toggle("is-scrolled", window.scrollY > 8);
    };

    syncNavShadow();
    window.addEventListener("scroll", syncNavShadow, { passive: true });

    if (navLinks.length > 0) {
        const currentPath = (window.location.pathname || "/").replace(/\/+$/, "") || "/";

        navLinks.forEach((link) => {
            let linkPath = "/";
            try {
                linkPath = new URL(link.href, window.location.origin).pathname.replace(/\/+$/, "") || "/";
            } catch (error) {
                linkPath = "/";
            }

            if (currentPath === linkPath || (linkPath !== "/" && currentPath.startsWith(`${linkPath}/`))) {
                link.classList.add("is-active");
            }
        });
    }

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
