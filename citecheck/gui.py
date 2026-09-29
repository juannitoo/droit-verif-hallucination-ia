"""The window, in two tabs: "check" (pick a document, read the report) and "keys" (enter
your access keys once). On first launch, with no key saved, it opens on the keys tab.

tkinter ships with Python: no extra dependency, and it behaves the same on Windows and
macOS. The check runs in a separate thread so the window does not freeze during network
calls.
"""
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from . import keys, reader, report
from .countries import COUNTRIES, DEFAULT
from .engine import check_document, valid_date
from .locales import t

LINK = "#1a55a0"
MUTED = "#555"


class Window:
    def __init__(self, root):
        self.root = root
        self.country = COUNTRIES[DEFAULT]
        self.document = None
        self.last = None
        self.queue = queue.Queue()
        root.title(t.TITLE)
        root.geometry("820x640")
        root.minsize(600, 440)

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)
        self.check_tab = ttk.Frame(self.tabs, padding=12)
        self.keys_tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.check_tab, text=t.TAB_CHECK)
        self.scope_tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.keys_tab, text=t.TAB_KEYS)
        self.tabs.add(self.scope_tab, text=t.TAB_SCOPE)

        self._build_check_tab()
        self._build_keys_tab()
        self._build_scope_tab()
        self.show_key_status()
        if not self._all_keys_present():
            self.tabs.select(self.keys_tab)

    # Tab "check"

    def _build_check_tab(self):
        tab = self.check_tab
        tab.columnconfigure(1, weight=1)

        ttk.Label(tab, text=t.DOCUMENT).grid(row=0, column=0, sticky="w")
        self.doc_label = ttk.Label(tab, text=t.NO_DOCUMENT)
        self.doc_label.grid(row=0, column=1, sticky="w", padx=8)
        ttk.Button(tab, text=t.CHOOSE, command=self.choose).grid(row=0, column=2)

        ttk.Label(tab, text=t.REFERENCE_DATE).grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.reference = ttk.Entry(tab, width=12)
        self.reference.grid(row=1, column=1, sticky="w", padx=8, pady=(10, 0))
        ttk.Label(tab, text=t.REFERENCE_HINT, foreground=MUTED).grid(
            row=2, column=1, columnspan=2, sticky="w", padx=8)
        ttk.Label(tab, text=t.IDCC).grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.idcc = ttk.Entry(tab, width=12)
        self.idcc.grid(row=3, column=1, sticky="w", padx=8, pady=(10, 0))
        ttk.Label(tab, text=t.IDCC_HINT, foreground=MUTED).grid(
            row=4, column=1, columnspan=2, sticky="w", padx=8)

        self.key_warning = ttk.Label(tab, text=t.KEYS_MISSING_WARNING, foreground=LINK,
                                     cursor="hand2", wraplength=700)
        self.key_warning.grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.key_warning.bind("<Button-1>", lambda e: self.tabs.select(self.keys_tab))

        self.button = ttk.Button(tab, text=t.CHECK, command=self.check, state="disabled")
        self.button.grid(row=6, column=0, columnspan=3, pady=12)

        self.output = ScrolledText(tab, wrap="word", font=("Courier", 10), state="disabled")
        self.output.grid(row=7, column=0, columnspan=3, sticky="nsew")
        tab.rowconfigure(7, weight=1)

        bottom = ttk.Frame(tab)
        bottom.grid(row=8, column=0, columnspan=3, pady=(10, 0))
        self.b_txt = ttk.Button(bottom, text=t.SAVE_TXT, state="disabled",
                                command=lambda: self.save("txt"))
        self.b_json = ttk.Button(bottom, text=t.SAVE_JSON, state="disabled",
                                 command=lambda: self.save("json"))
        self.b_txt.pack(side="left", padx=4)
        self.b_json.pack(side="left", padx=4)
        # Checked by default: a saved report travels, often to an online AI.
        self.no_excerpts = tk.BooleanVar(value=True)
        ttk.Checkbutton(tab, text=t.NO_EXCERPTS, variable=self.no_excerpts).grid(
            row=9, column=0, columnspan=3, pady=(8, 0))
        ttk.Label(tab, text=t.NO_EXCERPTS_HINT, foreground=MUTED, wraplength=740,
                  justify="center").grid(row=10, column=0, columnspan=3)

    # Tab "keys"

    def _build_keys_tab(self):
        tab = self.keys_tab
        tab.columnconfigure(1, weight=1)
        ttk.Label(tab, text=t.KEYS_EXPLANATION, wraplength=740, justify="left").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.fields = {}
        row = 1
        for name, label in self.country.KEYS.items():
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", pady=(10, 0))
            field = ttk.Entry(tab, show="•")
            field.grid(row=row, column=1, sticky="ew", padx=8, pady=(10, 0))
            buttons = ttk.Frame(tab)
            buttons.grid(row=row, column=2, pady=(10, 0))
            ttk.Button(buttons, text=t.KEY_SAVE,
                       command=lambda n=name: self.save_key(n)).pack(side="left")
            ttk.Button(buttons, text=t.KEY_DELETE,
                       command=lambda n=name: self.delete_key(n)).pack(side="left")
            status = ttk.Label(tab, foreground=MUTED)
            status.grid(row=row + 1, column=1, sticky="w", padx=8)
            self.fields[name] = (field, status)
            row += 2

        help_link = ttk.Label(tab, text=t.KEY_HELP, foreground=LINK, cursor="hand2")
        help_link.grid(row=row, column=1, sticky="w", padx=8, pady=(12, 0))
        help_link.bind("<Button-1>", lambda e: webbrowser.open(self.country.KEY_HELP_URL))

    # Tab "scope": generated from the country's own lists, so it cannot promise more
    # than the program does.

    def _build_scope_tab(self):
        box = ScrolledText(self.scope_tab, wrap="word", font=("TkDefaultFont", 10))
        box.pack(fill="both", expand=True)
        box.tag_configure("heading", font=("TkDefaultFont", 11, "bold"), spacing1=10,
                          spacing3=4)
        for heading, lines in self.country.scope():
            box.insert("end", heading + "\n", "heading")
            for line in lines:
                box.insert("end", f"  • {line}\n")
        box.config(state="disabled")

    def _all_keys_present(self):
        return all(keys.get(name) for name in self.country.KEYS)

    def show_key_status(self):
        for name, (field, status) in self.fields.items():
            status.config(text=t.KEY_PRESENT if keys.get(name) else t.KEY_MISSING)
        if self._all_keys_present():
            self.key_warning.grid_remove()
        else:
            self.key_warning.grid()

    def save_key(self, name):
        field, status = self.fields[name]
        value = field.get().strip()
        if not value:
            return
        field.delete(0, "end")
        if keys.save(name, value):
            self.show_key_status()
        else:
            status.config(text=t.KEY_NO_KEYRING)

    def delete_key(self, name):
        keys.delete(name)
        self.show_key_status()

    # Checking

    def choose(self):
        path = filedialog.askopenfilename(filetypes=[
            (t.FORMATS, "*.pdf *.docx *.odt *.txt *.md")])
        if path:
            self.document = path
            self.doc_label.config(text=path)
            self.button.config(state="normal")

    def write(self, text, clear=False):
        self.output.config(state="normal")
        if clear:
            self.output.delete("1.0", "end")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.config(state="disabled")

    def check(self):
        reference = self.reference.get().strip() or None
        if reference and not valid_date(reference):
            self.write(t.REFERENCE_INVALID + "\n", clear=True)
            return
        idcc = self.idcc.get().strip() or None
        if idcc and not idcc.isdigit():
            self.write(t.IDCC_INVALID + "\n", clear=True)
            return
        self.button.config(state="disabled")
        self.b_txt.config(state="disabled")
        self.b_json.config(state="disabled")
        self.write(t.IN_PROGRESS + "\n\n", clear=True)

        def work():
            try:
                r = check_document(self.document, log=lambda s: self.queue.put(("line", s)),
                                   options={"reference_date": reference, "idcc": idcc})
                self.queue.put(("done", r))
            except reader.Unreadable as e:
                self.queue.put(("error", str(e)))
            except Exception as e:
                self.queue.put(("error", f"{type(e).__name__} : {e}"))

        threading.Thread(target=work, daemon=True).start()
        self.root.after(100, self.poll)

    def poll(self):
        try:
            while True:
                kind, content = self.queue.get_nowait()
                if kind == "line":
                    self.write(content + "\n")
                elif kind == "error":
                    self.write("\n" + content + "\n")
                    self.button.config(state="normal")
                    return
                else:
                    self.last = content
                    self.write(report.to_text(content), clear=True)
                    self.button.config(state="normal")
                    self.b_txt.config(state="normal")
                    self.b_json.config(state="normal")
                    return
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def save(self, kind):
        path = filedialog.asksaveasfilename(
            defaultextension=f".{kind}", initialfile=f"{t.REPORT_FILE}.{kind}")
        if not path:
            return
        r = report.without_excerpts(self.last) if self.no_excerpts.get() else self.last
        content = report.to_json(r) if kind == "json" else report.to_text(r)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def run():
    root = tk.Tk()
    Window(root)
    root.mainloop()
    return 0
