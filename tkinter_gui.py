import json
import os
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, Tk

import audit_exporter
import audit_parser
from audit_system import check_custom_item, backup_registry, write_registry, restore_registry
from checkbox_treeview import CheckboxTreeview

MAX_N_SHOW_ITEM = 30000
FILETYPES = [("JSON files or AUDIT files", "*.json;*.audit"), ("All Files", "*.*")]


class TreeFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.tree = CheckboxTreeview(self, show='tree')
        self.tree.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.init_shortcuts()
        self.init_scroll_bars()
        self.bottom_frame = tk.Frame(self)
        self.search_box = tk.Entry(self.bottom_frame)
        self.init_bottom_frame()
        self.search_results = []
        self.search_index = 0
        self.check_results = ""

        self.popup = tk.Menu(self, tearoff=0)
        self.popup_selected = None
        self.init_popup()
        self.user_input = tk.StringVar()

    def remove_item(self):
        self.tree.delete([self.popup_selected])

    def edit_selected(self):
        item = self.tree.item(self.popup_selected)
        item['text'] = self.user_input.get()

    def show_edit_popup(self, event=None):
        win = tk.Toplevel()
        win.geometry('400x100')
        win.wm_title("Window")
        item_text = self.tree.item(self.popup_selected)['text']
        info_text = tk.Label(win, text="Entry text:")
        info_text.grid(row=0, column=0)
        edit_box = tk.Entry(win, width=800, textvariable=self.user_input)
        edit_box.delete(0, 'end')
        edit_box.insert(0, item_text)
        edit_box.grid(row=0, column=1)

        def local_fun():
            win.destroy()
            self.edit_selected()

        okay_button = ttk.Button(win, text="Okay", command=local_fun)
        okay_button.grid(row=2, column=0)
        cancel_button = ttk.Button(win, text="Cancel", command=win.destroy)
        cancel_button.grid(row=0, column=2)

    def init_popup(self):
        self.tree.bind("<Button-3>", self.show_popup)
        self.popup.add_command(label="Edit Entry", command=self.show_edit_popup)
        # self.popup.add_command(label="Add entry", command=None)
        self.popup.add_command(label="Delete entry", command=self.remove_item)

    def show_popup(self, event):
        self.tree.selection_set(self.tree.identify_row(event.y))  # Before popping up selecting the clicked item
        selection = self.tree.selection()
        if selection:
            self.tree.item(selection, open=True)
            self.popup_selected = selection
            self.popup.post(event.x_root, event.y_root)

    def init_scroll_bars(self):
        ysb = ttk.Scrollbar(
            self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=ysb.set)

        xsb = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(xscroll=xsb.set)

        ysb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        xsb.grid(row=1, column=0, sticky=(tk.E, tk.W))

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def init_bottom_frame(self):
        self.bottom_frame.grid(column=0, row=1, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.bottom_frame.bind_all("<Control-f>", self.toggle_search_box)
        search_label = tk.Label(self.bottom_frame, text="Search:")
        search_label.pack(side=tk.LEFT)

        button_frame = tk.Frame(self.bottom_frame)
        button_frame.pack(side=tk.RIGHT)

        search_button = tk.Button(button_frame, text="Search")
        search_button.pack(side=tk.LEFT)
        search_button.bind('<Button-1>', self.find_word)

        next_button = tk.Button(button_frame, text="Next")
        next_button.pack(side=tk.RIGHT)
        next_button.bind('<Button-1>', self.view_next_search_result)

        prev_button = tk.Button(button_frame, text="Prev")
        prev_button.pack(side=tk.LEFT)
        prev_button.bind('<Button-1>', self.view_previous_search_result)

        self.search_box.pack(fill='x')
        self.search_box.bind('<KeyPress-Return>', self.find_word)

    def find_word(self, event=None):
        search_text = self.search_box.get()
        if not search_text:
            return
        self.collapse_all(None)
        # search_children = []
        # for selection in self.tree.selection():
        #     search_children += (list(self.get_all_children(self.tree, item=selection)))
        # if len(search_children):
        search_children = self.get_all_children(self.tree)
        self.search_results = []
        self.search_index = 0
        for item_id in search_children:
            item_text = self.tree.item(item_id, 'text')
            item_text = str(item_text)
            if search_text.lower() in item_text.lower():
                # self.tree.see(item_id)
                self.tree.item(item_id, open=True)
                self.search_results.append(item_id)
        self.view_next_search_result()

    def view_next_search_result(self, event=None):
        if len(self.search_results):
            current_id = self.search_results[self.search_index]
            self.tree.see(current_id)
            # self.tree.selection_clear()
            self.tree.selection_set(current_id)
            # self.tree.selection_add(current_id)
            self.search_index += 1
            self.search_index %= len(self.search_results)

    def view_previous_search_result(self, event=None):
        if len(self.search_results):
            self.search_index -= 1
            self.search_index %= len(self.search_results)
            current_id = self.search_results[self.search_index]
            self.tree.see(current_id)
            # self.tree.selection_clear()
            self.tree.selection_set(current_id)

            # self.tree.selection_add(current_id)

    def get_all_children(self, tree, item=""):
        children = tree.get_children(item)
        for child in children:
            children += self.get_all_children(tree, child)
        return children

    def set_data(self, json_data):
        # Delete all tree nodes
        for i in self.tree.get_children():
            self.tree.delete(i)

        parent = ""
        if isinstance(json_data, list):
            for index, value in enumerate(json_data):
                self.insert_node(parent, index, value)
        elif isinstance(json_data, dict):
            for (key, value) in json_data.items():
                self.insert_node(parent, key, value)

    def insert_node(self, parent, key, value):
        node = self.tree.insert(parent, 'end', None, text=key, open=False)
        if value is None:
            return

        if type(value) in (list, tuple):
            for index, item in enumerate(value[:MAX_N_SHOW_ITEM]):
                self.insert_node(node, index, item)
        elif isinstance(value, dict):
            for key, item in value.items():
                self.insert_node(node, key, item)
        else:
            self.tree.insert(parent=node, index='end', text=value, open=False)

    def toggle_search_box(self, event=None):
        if self.bottom_frame.winfo_manager():
            self.bottom_frame.grid_forget()
        else:
            self.bottom_frame.grid(column=0, row=1, sticky=(tk.N, tk.S, tk.E, tk.W))

    def expand_all(self, event=None):
        """
        :param event: event arg (not used)
        """
        for item in self.get_all_children(self.tree):
            self.tree.item(item, open=True)

    def collapse_all(self, event=None):
        """
        :param event: event arg (not used)
        """
        for item in self.get_all_children(self.tree):
            self.tree.item(item, open=False)

    def open_json_file(self, filename):
        with open(filename, encoding='utf-8') as f:
            json_data = json.load(f)
        self.set_data(json_data)

    def open_file_tool(self):
        file_path = filedialog.askopenfilename(
            initialdir=os.getcwd(),
            filetypes=FILETYPES)
        if file_path != "":
            if '.audit' in file_path:
                self.set_data(audit_parser.get_json_from_audit(file_path))
            else:
                self.open_json_file(file_path)

    def init_shortcuts(self):
        self.master.bind("<Control-e>", self.expand_all)
        self.master.bind("<Control-l>", self.collapse_all)
        self.master.bind("<Control-o>", self.open_file_tool)
        # TODO REMOVE THESE:
        self.master.bind("<Control-c>",
                         lambda e: self.set_data(audit_parser.get_json_from_audit('MSCT_Windows_10_2004_v1.0.0.audit')))
        self.master.bind("<Control-x>", lambda e: self.audit_system())

    def recursive_dict(self, index):
        childrens = self.tree.get_children(index)

        if len(childrens) > 1:
            # Is dictionary
            ret = {}
            for child in childrens:
                if self.tree.item(child, 'tags')[0] == 'unchecked':
                    continue
                key, value = self.recursive_dict(child)
                ret[key] = value
            return self.tree.item(index, 'text'), ret
        else:
            # Is parameter or modifier
            children_of_children = self.tree.get_children(childrens)
            if len(children_of_children) != 0 and index not in children_of_children:
                key, val = self.recursive_dict(childrens)
                return self.tree.item(index, 'text'), {key: val}
            return self.tree.item(index, 'text'), self.tree.item(childrens, 'text')

    def get_json_dict(self, get_checked_only=True):
        ret = {}
        for child in self.tree.get_children():
            if get_checked_only:
                if self.tree.item(child, 'tags')[0] == 'unchecked':
                    continue
            key, value = self.recursive_dict(child)
            ret[key] = value
        return ret

    def save_json(self):
        f = tk.filedialog.asksaveasfile(mode='w', filetypes=[("JSON files", "*.json")], defaultextension=".json")
        if f is None:  # asksaveasfile return `None` if dialog closed with "cancel".
            return
        json.dump(self.get_json_dict(), f, indent=1)
        f.close()

    def export_audit(self):
        f = tk.filedialog.asksaveasfile(mode='w', filetypes=[("AUDIT files", "*.audit")], defaultextension=".audit")
        if f is None:  # asksaveasfile return `None` if dialog closed with "cancel".
            return

        audit_exporter.export_audit(f, self.get_json_dict())
        f.close()

    def check_all(self):
        for child in self.tree.get_children():
            self.tree.check_ancestor(child)
            self.tree.check_descendant(child)

    def uncheck_all(self):
        for child in self.tree.get_children():
            self.tree.uncheck_ancestor(child)
            self.tree.uncheck_descendant(child)

    def update_dict(self, json_dict=None):
        if json_dict is None:
            json_dict = self.get_json_dict(get_checked_only=False)
        custom_item_iterator = get_custom_items(json_dict)
        results = {"passed": {}, "failed": {}, "unknown": {}}
        for custom_item in custom_item_iterator:
            check_custom_item(custom_item, results)

        self.set_data(results)
        self.check_results = self.get_check_info()

    def audit_system(self):

        root = tk.Toplevel(self)
        root.geometry('500x500')
        root.wm_title("Check audit")
        menubar = tk.Menu(root)
        app = TreeFrame(root)
        app.update_dict(self.get_json_dict())

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save Json", accelerator='Ctrl+S', command=app.save_json)
        menubar.add_cascade(label="File", menu=file_menu)
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Expand All", accelerator="Ctrl+E", command=app.expand_all)
        tools_menu.add_command(label="Collapse All", accelerator="Ctrl+L", command=app.collapse_all)
        tools_menu.add_command(label="Check All", command=app.check_all)
        tools_menu.add_command(label="Uncheck All", command=app.uncheck_all)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        audit_menu = tk.Menu(menubar, tearoff=0)
        audit_menu.add_command(label="Write registry", command=app.write_registry)
        audit_menu.add_command(label="Backup registry", command=app.backup_registry)
        audit_menu.add_command(label="Restore registry", command=app.restore_registry)

        def update_menubar():
            app.update_dict()
            menubar.entryconfigure(4, label=app.check_results)
            pass

        audit_menu.add_command(label="Recheck audit", command=update_menubar)

        menubar.add_cascade(label="Audit", menu=audit_menu)

        app.grid(column=0, row=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        root.config(menu=menubar)

        results_label = tk.Label(menubar, text=app.check_results, relief=tk.RAISED)
        results_label.pack(side=tk.RIGHT)

        menubar.add_command(label=app.check_results)

        # menubar.add_command(label=app.check_results, command=app.update_dict)

    def get_check_info(self):
        info_dict = self.get_json_dict()
        passed_num = len(info_dict['passed'])
        failed_num = len(info_dict['failed'])
        unk_num = len(info_dict['unknown'])
        return f"Passed: {passed_num}/{passed_num + failed_num} Unknown:{unk_num}"

    def write_registry(self):
        write_registry(self.get_json_dict())

    def backup_registry(self):
        backup_registry(self.get_json_dict())

    def restore_registry(self):
        restore_registry(self.get_json_dict())


def get_custom_items(dictionary):
    for key, value in dictionary.items():
        if type(value) is dict:
            if "custom_item" in key:
                yield value
            else:
                yield from get_custom_items(value)


def run_gui():
    root: Tk = tk.Tk()
    root.title('Audit Parser-Exporter')
    root.geometry("600x500")
    menubar = tk.Menu(root)
    app = TreeFrame(root)

    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="Open", accelerator='Ctrl+O',
                          command=app.open_file_tool)
    file_menu.add_command(label="Save Json", accelerator='Ctrl+S', command=app.save_json)
    file_menu.add_command(label="Export Audit", command=app.export_audit)
    menubar.add_cascade(label="File", menu=file_menu)

    tools_menu = tk.Menu(menubar, tearoff=0)
    tools_menu.add_command(label="Expand All", accelerator="Ctrl+E", command=app.expand_all)
    tools_menu.add_command(label="Collapse All", accelerator="Ctrl+L", command=app.collapse_all)
    tools_menu.add_command(label="Check All", command=app.check_all)
    tools_menu.add_command(label="Uncheck All", command=app.uncheck_all)
    menubar.add_cascade(label="Tools", menu=tools_menu)

    menubar.add_command(label="Audit System", command=app.audit_system)

    app.grid(column=0, row=0, sticky=(tk.N, tk.S, tk.E, tk.W))
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    root.config(menu=menubar)
    root.mainloop()
