import io
import json
import threading
import tkinter as tk
import unicodedata
import urllib.request
from pathlib import Path
from tkinter import ttk

try:
    from PIL import Image, ImageTk
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


DATA_PATH = Path("data/warframes.json")
RELICS_PATH = Path("data/relic-drops.json")
WEAPON_PATH = Path("data/weapons.json")


def normalize(text):
    text = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def format_number(value, decimals=2):
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return str(value)


def format_percent(value):
    if value is None:
        return "N/A"
    return f"{format_number(value * 100, 1)}%"


def weapon_stats_text(weapon):
    stats = weapon.get("attackStats") or {}
    lines = [
        ("Critical Chance", format_percent(stats.get("criticalChance"))),
        ("Critical Multiplier", f"{format_number(stats.get('criticalMultiplier'))}x"
            if stats.get("criticalMultiplier") is not None else "N/A"),
        ("Status Chance", format_percent(stats.get("statusChance"))),
    ]
    if weapon.get("isMelee"):
        lines += [
            ("Attack Speed", format_number(stats.get("attackSpeed"))),
            ("Range", format_number(stats.get("range"))),
            ("Slam Attack", format_number(stats.get("slamAttack"))),
            ("Heavy Attack", format_number(stats.get("heavyAttack"))),
            ("Heavy Slam Attack", format_number(stats.get("heavySlamAttack"))),
            ("Wind Up", format_number(stats.get("windUp"))),
            ("Combo Duration", format_number(stats.get("comboDuration"))),
            ("Follow Through", format_number(stats.get("followThrough"))),
            ("Stance Polarity", format_number(stats.get("stancePolarity"))),
        ]
    else:
        lines += [
            ("Fire Rate", format_number(stats.get("fireRate"))),
            ("Magazine Size", format_number(stats.get("magazine"))),
            ("Reload Time", format_number(stats.get("reload"))),
            ("Accuracy", format_number(stats.get("accuracy"))),
            ("Multishot", format_number(stats.get("multishot"))),
            ("Punch Through", format_number(stats.get("punchThrough"))),
            ("Noise", format_number(stats.get("noise"))),
            ("Trigger", format_number(stats.get("trigger"))),
        ]
    return "".join(f"{label}: {value}\n" for label, value in lines)


class RelicWindow(tk.Toplevel):
    def __init__(self, parent, frame, active_relics, vaulted_relics):
        super().__init__(parent)
        self.title(f"Relics - {frame['name']}")
        self.geometry("780x580")
        self.active_relics = active_relics
        self.vaulted_relics = vaulted_relics
        self.relic_by_item = {}

        status = "Vaulted" if frame.get("vaulted") else "Available"
        ttk.Label(
            self, text=f"{frame['name']} - {status}", font=("Segoe UI", 14, "bold"), padding=8
        ).pack(anchor="w")

        self.parts_tree = ttk.Treeview(
            self, columns=("rarity", "status"), selectmode="browse", height=12
        )
        self.parts_tree.heading("#0", text="Part / Relic")
        self.parts_tree.heading("rarity", text="Rarity")
        self.parts_tree.heading("status", text="Status")
        self.parts_tree.column("#0", width=320)
        self.parts_tree.column("rarity", width=120, anchor="center")
        self.parts_tree.column("status", width=120, anchor="center")
        self.parts_tree.tag_configure("part", font=("Segoe UI", 10, "bold"))
        self.parts_tree.tag_configure("vaulted", foreground="#888888")
        self.parts_tree.pack(fill="both", expand=True, padx=8)
        self.parts_tree.bind("<<TreeviewSelect>>", self._on_select)

        self.info_var = tk.StringVar(value="Select a relic to see where it drops.")
        ttk.Label(self, textvariable=self.info_var, padding=8, justify="left").pack(anchor="w")

        columns = ("mission", "rotation", "rarity", "chance")
        self.drops_tree = ttk.Treeview(self, columns=columns, show="headings", height=8)
        for column, title, width in zip(
            columns, ("Mission", "Rotation", "Rarity", "Chance"), (300, 100, 100, 80)
        ):
            self.drops_tree.heading(column, text=title)
            self.drops_tree.column(column, width=width)
        self.drops_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._fill_parts(frame.get("components") or [])

    def _fill_parts(self, components):
        for component in components:
            if not component.get("relics"):
                continue
            ducats = component.get("ducats")
            suffix = f" ({ducats} ducats)" if ducats is not None else ""
            parent = self.parts_tree.insert(
                "", "end", text=f"{component['name']}{suffix}", open=True, tags=("part",)
            )
            relics = sorted(
                component.get("relics") or [],
                key=lambda r: (r["relic"] in self.vaulted_relics, r["relic"]),
            )
            for relic in relics:
                is_vaulted = relic["relic"] not in self.active_relics
                item = self.parts_tree.insert(
                    parent,
                    "end",
                    text=relic["relic"],
                    values=(relic["rarity"], "Vaulted" if is_vaulted else "Active"),
                    tags=("vaulted",) if is_vaulted else (),
                )
                self.relic_by_item[item] = relic

    def _on_select(self, _event):
        self.drops_tree.delete(*self.drops_tree.get_children())
        selection = self.parts_tree.selection()
        relic = self.relic_by_item.get(selection[0]) if selection else None
        if relic is None:
            self.info_var.set("Select a relic to see where it drops.")
            return

        chances = " | ".join(f"{name}: {value}%" for name, value in relic["chances"].items())
        drops = self.active_relics.get(relic["relic"])
        if drops is None:
            self.info_var.set(
                f"{relic['relic']} is vaulted and no longer drops.\nPart chance - {chances}"
            )
            return

        self.info_var.set(f"{relic['relic']} drops from:\nPart chance - {chances}")
        for drop in sorted(drops, key=lambda d: -d["chance"]):
            self.drops_tree.insert(
                "",
                "end",
                values=(drop["mission"], drop["rotation"] or "-", drop["rarity"], f"{drop['chance']}%"),
            )


# First instance of the menu :p
class MenuScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        center = ttk.Frame(self)
        center.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(center, text="Orokin Grand Library", font=("Segoe UI", 18, "bold")).pack(pady=(0, 16))

        ttk.Button(
            center, text="Warframes", style="Big.TButton",
            command=lambda: controller.show_screen("warframes"),
        ).pack(fill="x", pady=6)
        ttk.Button(
            center, text="Weapons", style="Big.TButton",
            command=lambda: controller.show_screen("weapons"),
        ).pack(fill="x", pady=6)


# Placeholder menu will update it later
class PlaceholderMenu(ttk.Frame):
    def __init__(self, parent, controller, title):
        super().__init__(parent)
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="← Menu", command=lambda: controller.show_screen("menu")).pack(side="left")
        ttk.Label(self, text=title, font=("Segoe UI", 14, "bold")).pack(expand=True)


class WeaponScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        with open(WEAPON_PATH, encoding="utf-8") as fw:
            self.data = sorted(json.load(fw), key=lambda w: w["name"])
        with open(RELICS_PATH, encoding="utf-8") as fr:
            relic_data = json.load(fr)
        self.active_relics = relic_data["activeRelics"]
        self.vaulted_relics = set(relic_data["vaultedRelics"])

        self.visible = list(self.data)
        self.image_cache = {}
        self.current = None
        self.relic_window = None

        self._create_ui()
        self._fill_list()

    def _create_ui(self):
        top = ttk.Frame(self, padding=8)
        top.pack(side="top", fill="x")
        ttk.Button(
            top, text="← Menu", command=lambda: self.controller.show_screen("menu")
        ).pack(side="left")

        left = ttk.Frame(self, padding=8)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Search:").pack(anchor="w")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter())
        ttk.Entry(left, textvariable=self.search_var, width=28).pack(fill="x", pady=(0, 6))

        self.prime_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            left, text="Prime only", variable=self.prime_var, command=self._filter
        ).pack(anchor="w", pady=(0, 6))

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, exportselection=False)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        self.count_label = ttk.Label(left, text="")
        self.count_label.pack(anchor="w", pady=(6, 0))

        right = ttk.Frame(self, padding=8)
        right.pack(side="right", fill="both", expand=True)

        header = ttk.Frame(right)
        header.pack(fill="x")
        self.image_label = ttk.Label(header)
        self.image_label.pack(side="left", padx=(0, 12))
        texts = ttk.Frame(header)
        texts.pack(side="left", fill="x", expand=True)
        self.name_label = ttk.Label(texts, text="Select a weapon", font=("Segoe UI", 18, "bold"))
        self.name_label.pack(anchor="w")
        self.subtitle_label = ttk.Label(texts, text="", wraplength=520, justify="left")
        self.subtitle_label.pack(anchor="w")

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True, pady=(10, 0))
        self.summary_text = self._create_tab("Summary")
        self.acquisition_text = self._create_tab("How to get it")

    def _create_tab(self, title):
        frame = ttk.Frame(self.tabs)
        self.tabs.add(frame, text=title)
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        text = tk.Text(frame, wrap="word", yscrollcommand=scrollbar.set, padx=8, pady=8, state="disabled")
        text.pack(fill="both", expand=True)
        scrollbar.config(command=text.yview)
        text.tag_configure("heading", font=("Segoe UI", 11, "bold"))
        text.tag_configure("link", foreground="#1a73e8", underline=True)
        text.tag_bind("link", "<Button-1>", self._open_relics)
        text.tag_bind("link", "<Enter>", lambda e, t=text: t.config(cursor="hand2"))
        text.tag_bind("link", "<Leave>", lambda e, t=text: t.config(cursor=""))
        return text

    def _filter(self):
        query = normalize(self.search_var.get())
        prime_only = self.prime_var.get()
        self.visible = [
            w for w in self.data
            if query in normalize(w["name"]) and (not prime_only or w.get("isPrime"))
        ]
        self._fill_list()

    def _fill_list(self):
        self.listbox.delete(0, "end")
        for w in self.visible:
            self.listbox.insert("end", w["name"])
        self.count_label.config(text=f"{len(self.visible)} of {len(self.data)}")

    def _on_select(self, _event):
        selection = self.listbox.curselection()
        if selection:
            self._show(self.visible[selection[0]])

    def _write(self, widget, parts):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        for content, tag in parts:
            widget.insert("end", content, tag) if tag else widget.insert("end", content)
        widget.config(state="disabled")

    def _show(self, w):
        self.current = w
        self.name_label.config(text=w["name"])
        self.subtitle_label.config(
            text=f"{w.get('slot')} - {w.get('type')} | Required mastery rank: {w.get('masteryReq')}"
        )
        self._load_image(w)

        self._write(self.summary_text, [
            ("Description\n", "heading"), (f"{w.get('description') or 'No description.'}\n\n", None),
            ("Stats\n", "heading"), (weapon_stats_text(w) + "\n", None),
            ("Wiki\n", "heading"), (f"{w.get('wikiUrl') or 'N/A'}\n", None),
        ])

        has_relics = any(c.get("relics") for c in w.get("components") or [])
        parts = []
        for source in w.get("acquisition") or []:
            is_relic_link = w.get("isPrime") and has_relics and source.get("type") == "Void Relic"
            tags = ("heading", "link") if is_relic_link else "heading"
            parts.append((f"[{source.get('type')}] {source.get('method')}\n", tags))
            parts.append((f"{source.get('detail')}\n\n", None))
            if is_relic_link:
                parts.append(("Click the title above to see parts, relics and drop locations.\n\n", None))
        self._write(self.acquisition_text, parts or [("No data.", None)])

    def _open_relics(self, _event):
        if not self.current or not self.current.get("isPrime"):
            return
        if self.relic_window is not None and self.relic_window.winfo_exists():
            self.relic_window.destroy()
        self.relic_window = RelicWindow(
            self, self.current, self.active_relics, self.vaulted_relics
        )

    def _load_image(self, w):
        self.image_label.config(image="")
        if not HAS_PILLOW or not w.get("imageUrl"):
            return
        url = w["imageUrl"]
        if url in self.image_cache:
            self.image_label.config(image=self.image_cache[url])
            return
        threading.Thread(target=self._download, args=(url, w["name"]), daemon=True).start()

    def _download(self, url, name):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=10) as response:
                image = Image.open(io.BytesIO(response.read())).convert("RGBA")
            image.thumbnail((110, 110))
            self.after(0, self._set_image, url, image, name)
        except Exception:
            pass

    def _set_image(self, url, image, name):
        photo = ImageTk.PhotoImage(image)
        self.image_cache[url] = photo
        if self.current and self.current["name"] == name:
            self.image_label.config(image=photo)


class WarframeScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        with open(DATA_PATH, encoding="utf-8") as f:
            self.data = sorted(json.load(f), key=lambda w: w["name"])
        with open(RELICS_PATH, encoding="utf-8") as f:
            relic_data = json.load(f)
        self.active_relics = relic_data["activeRelics"]
        self.vaulted_relics = set(relic_data["vaultedRelics"])

        self.visible = list(self.data)
        self.image_cache = {}
        self.current = None
        self.relic_window = None

        self._create_ui()
        self._fill_list()

    def _create_ui(self):
        top = ttk.Frame(self, padding=8)
        top.pack(side="top", fill="x")
        ttk.Button(
            top, text="← Menu", command=lambda: self.controller.show_screen("menu")
        ).pack(side="left")

        left = ttk.Frame(self, padding=8)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Search:").pack(anchor="w")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter())
        ttk.Entry(left, textvariable=self.search_var, width=28).pack(fill="x", pady=(0, 6))

        self.prime_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            left, text="Prime only", variable=self.prime_var, command=self._filter
        ).pack(anchor="w", pady=(0, 6))

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, exportselection=False)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        self.count_label = ttk.Label(left, text="")
        self.count_label.pack(anchor="w", pady=(6, 0))

        right = ttk.Frame(self, padding=8)
        right.pack(side="right", fill="both", expand=True)

        header = ttk.Frame(right)
        header.pack(fill="x")
        self.image_label = ttk.Label(header)
        self.image_label.pack(side="left", padx=(0, 12))
        texts = ttk.Frame(header)
        texts.pack(side="left", fill="x", expand=True)
        self.name_label = ttk.Label(texts, text="Select a warframe", font=("Segoe UI", 18, "bold"))
        self.name_label.pack(anchor="w")
        self.subtitle_label = ttk.Label(texts, text="", wraplength=520, justify="left")
        self.subtitle_label.pack(anchor="w")

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True, pady=(10, 0))
        self.summary_text = self._create_tab("Summary")
        self.abilities_text = self._create_tab("Abilities")
        self.acquisition_text = self._create_tab("How to get it")

    def _create_tab(self, title):
        frame = ttk.Frame(self.tabs)
        self.tabs.add(frame, text=title)
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        text = tk.Text(frame, wrap="word", yscrollcommand=scrollbar.set, padx=8, pady=8, state="disabled")
        text.pack(fill="both", expand=True)
        scrollbar.config(command=text.yview)
        text.tag_configure("heading", font=("Segoe UI", 11, "bold"))
        text.tag_configure("link", foreground="#1a73e8", underline=True)
        text.tag_bind("link", "<Button-1>", self._open_relics)
        text.tag_bind("link", "<Enter>", lambda e, t=text: t.config(cursor="hand2"))
        text.tag_bind("link", "<Leave>", lambda e, t=text: t.config(cursor=""))
        return text

    def _filter(self):
        query = normalize(self.search_var.get())
        prime_only = self.prime_var.get()
        self.visible = [
            w for w in self.data
            if query in normalize(w["name"]) and (not prime_only or w.get("isPrime"))
        ]
        self._fill_list()

    def _fill_list(self):
        self.listbox.delete(0, "end")
        for w in self.visible:
            self.listbox.insert("end", w["name"])
        self.count_label.config(text=f"{len(self.visible)} of {len(self.data)}")

    def _on_select(self, _event):
        selection = self.listbox.curselection()
        if selection:
            self._show(self.visible[selection[0]])

    def _write(self, widget, parts):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        for content, tag in parts:
            widget.insert("end", content, tag) if tag else widget.insert("end", content)
        widget.config(state="disabled")

    def _show(self, w):
        self.current = w
        self.name_label.config(text=w["name"])
        self.subtitle_label.config(text=f"Required mastery rank: {w.get('masteryReq')}")
        self._load_image(w)

        stats = (
            f"Health: {w.get('health')}\nShield: {w.get('shield')}\n"
            f"Armor: {w.get('armor')}\nEnergy: {w.get('energy')}\n"
            f"Sprint: {w.get('sprint')}\n"
        )
        variants = ", ".join(f"{v['name']} ({v['type']})" for v in w.get("variants") or []) or "None"
        self._write(self.summary_text, [
            ("Description\n", "heading"), (f"{w.get('description', '')}\n\n", None),
            ("Stats\n", "heading"), (stats + "\n", None),
            ("Variants\n", "heading"), (variants + "\n\n", None),
            ("Wiki\n", "heading"), (f"{w.get('wikiUrl')}\n", None),
        ])

        parts = []
        for i, ability in enumerate(w.get("abilities", []), 1):
            parts += [(f"{i}. {ability['name']}\n", "heading"), (f"{ability['description']}\n\n", None)]
        self._write(self.abilities_text, parts or [("No data.", None)])

        parts = []
        for source in w.get("acquisition") or []:
            is_relic_link = w.get("isPrime") and source.get("type") == "Void Relic"
            tags = ("heading", "link") if is_relic_link else "heading"
            parts.append((f"[{source.get('type')}] {source.get('method')}\n", tags))
            parts.append((f"{source.get('detail')}\n\n", None))
            if is_relic_link:
                parts.append(("Click the title above to see parts, relics and drop locations.\n\n", None))
        self._write(self.acquisition_text, parts or [("No data.", None)])

    def _open_relics(self, _event):
        if not self.current or not self.current.get("isPrime"):
            return
        if self.relic_window is not None and self.relic_window.winfo_exists():
            self.relic_window.destroy()
        self.relic_window = RelicWindow(
            self, self.current, self.active_relics, self.vaulted_relics
        )

    def _load_image(self, w):
        self.image_label.config(image="")
        if not HAS_PILLOW or not w.get("imageUrl"):
            return
        url = w["imageUrl"]
        if url in self.image_cache:
            self.image_label.config(image=self.image_cache[url])
            return
        threading.Thread(target=self._download, args=(url, w["name"]), daemon=True).start()

    def _download(self, url, name):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=10) as response:
                image = Image.open(io.BytesIO(response.read())).convert("RGBA")
            image.thumbnail((110, 110))
            self.after(0, self._set_image, url, image, name)
        except Exception:
            pass

    def _set_image(self, url, image, name):
        photo = ImageTk.PhotoImage(image)
        self.image_cache[url] = photo
        if self.current and self.current["name"] == name:
            self.image_label.config(image=photo)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Orokin Grand Library")
        self.geometry("1600x900")
        self.minsize(700, 450)

        style = ttk.Style(self)
        style.configure("Big.TButton", font=("Segoe UI", 14), padding=(40, 14))

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.titles = {
            "menu": "Orokin Grand Library",
            "warframes": "Orokin Grand Library - Warframes",
            "weapons": "Orokin Grand Library - Weapons",
        }
        self.screens = {
            "menu": MenuScreen(container, self),
            "warframes": WarframeScreen(container, self),
            "weapons": WeaponScreen(container, self),
        }
        for screen in self.screens.values():
            screen.grid(row=0, column=0, sticky="nsew")

        self.show_screen("menu")

    def show_screen(self, name):
        self.screens[name].tkraise()
        self.title(self.titles[name])


if __name__ == "__main__":
    App().mainloop()
