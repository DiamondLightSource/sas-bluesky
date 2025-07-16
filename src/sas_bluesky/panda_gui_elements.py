#!/dls/science/users/akz63626/i22/i22_venv/bin/python


"""

Python Elements for NCD PandA config GUI

"""

import tkinter
from tkinter import messagebox, ttk

from dodal.utils import get_beamline_name
from ophyd_async.fastcs.panda import (
    SeqTrigger,
)
from ophyd_async.fastcs.panda._block import PandaTimeUnits

from sas_bluesky.defaults_configs import (
    default_group,
    default_profile,
    get_devices,
    get_gui,
    get_plan_params,
)
from sas_bluesky.profile_groups import Group, Profile
from sas_bluesky.utils.ncdcore import ncdcore
from sas_bluesky.utils.utils import (
    ProfilePlotter,
)

BL = get_beamline_name("i22")
gui_config = get_gui(BL)
default_devices = get_devices(BL)
plan_params = get_plan_params(BL)
group = default_group(BL)
profile = default_profile(BL)


class EditableTableview(ttk.Treeview):
    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        super().__init__(parent, *args, **kwargs)
        self.bind("<Double-1>", lambda event: self.onDoubleClick(event))
        self.kwargs = kwargs

    def onDoubleClick(self, event):
        """Executed, when a row is double-clicked. Opens
        read-only EntryPopup above the item's column, so it is possible
        to select text"""

        # close previous popups
        try:  # in case there was no previous popup
            self.Popup.destroy()
        except AttributeError:
            pass

        # what row and column was clicked on
        rowid = self.identify_row(event.y)
        column = self.identify_column(event.x)

        # get column position info
        bbox = self.bbox(rowid, column)
        if isinstance(bbox, str):
            raise ValueError("Bounding box invalid")
        else:
            x, y, width, height = bbox

        # y-axis offset
        pady = height // 2

        text = self.item(rowid, "values")[int(column[1:]) - 1]

        # handle exception when header is double click
        if not rowid:
            return
        # row 1 is the group name and should just be group-n and increments
        # for each new one
        elif column == "#1":
            return

        elif column in ["#4", "#6"]:  # these groups create a drop down menu
            # place dropdown popup properly
            options = list(PandaTimeUnits.__dict__["_member_names_"])
            # options = [f.lower() for f in options]

            self.Popup = DropdownPopup(self, rowid, int(column[1:]) - 1, text, options)
            self.Popup.place(x=x, y=y + pady, width=width, height=height, anchor="w")

        elif column in ["#7"]:  # these groups create a drop down menu
            # place dropdown popup properly

            options = list(SeqTrigger.__dict__["_member_names_"])

            # options = ["True", "False"]
            self.Popup = DropdownPopup(self, rowid, int(column[1:]) - 1, text, options)
            self.Popup.place(x=x, y=y + pady, width=width, height=height, anchor="w")

        elif column in ["#8", "#9"]:
            if not gui_config.PULSE_BLOCK_AS_ENTRY_BOX:
                self.Popup = CheckButtonPopup(
                    self,
                    rowid,
                    int(column[1:]) - 1,
                    x=x,
                    y=y,
                    columns=self.kwargs["columns"],
                )
            if gui_config.PULSE_BLOCK_AS_ENTRY_BOX:
                self.Popup = EntryPopup(self, rowid, int(column[1:]) - 1, text)
                self.Popup.place(
                    x=x, y=y + pady, width=width, height=height, anchor="w"
                )

        else:
            # place Entry popup properly
            self.Popup = EntryPopup(
                self, rowid, int(column[1:]) - 1, text, entrytype=int
            )
            self.Popup.place(x=x, y=y + pady, width=width, height=height, anchor="w")

        return


class DropdownPopup(ttk.Combobox):
    def __init__(self, parent, rowid, column, text, options, **kw):
        ttk.Style().configure("pad.TEntry", padding="1 1 1 1")

        self.option_var = tkinter.StringVar()
        self.tv = parent
        self.rowid = rowid
        self.column = column

        super().__init__(
            parent, textvariable=self.option_var, values=options, state="readonly"
        )

        self.current(options.index(text))

        # self.event_generate('<Button-1>')

        self.bind("<Return>", self.on_return)
        self.bind("<Escape>", lambda *ignore: self.destroy())
        self.bind("<<ComboboxSelected>>", self.on_return)
        self.focus_force()

    def on_return(self, event):
        rowid = self.tv.focus()
        vals = self.tv.item(rowid, "values")
        vals = list(vals)

        selection = ncdcore.str2bool(self.option_var.get())

        if selection is not None:
            vals[self.column] = selection
        else:
            selection = self.option_var.get()
            vals[self.column] = self.option_var.get()

        self.selection = selection

        self.tv.item(rowid, values=vals)
        self.destroy()

        self.tv.parent.parent.commit_config()
        self.tv.parent.profile.analyse_profile()
        self.tv.parent.generate_info_boxes()


class CheckButtonPopup(ttk.Checkbutton):
    def __init__(self, parent, rowid, column, x, y, columns, **kw):
        self.parent: EditableTableview = parent
        self.rowid: int = rowid
        self.column: int = column

        self.row_num = int(rowid[-2::], 16) - 1

        w = 420  # width for the Tk root
        h = 50  # height for the Tk root

        self.root = tkinter.Toplevel()  ##HOLY MOLY
        # THIS WAS TK.TK AND IT WAS CAUSING SO MANY ISSUES,
        # USE TOPLEVEL WHEN OPENING NEW TEMP WINDOW.
        # IT WAS CUASING THE CHECKBUTTON TO ASSIGN TO SOMETHING ELSE.
        # SEE https://stackoverflow.com/questions/55208876/tkinter-set-and-get-not-working-in-a-window-inside-a-window

        self.root.minsize(w, h)
        self.root.title(f"{columns[column]} - Group: {self.row_num}")

        vals = self.parent.item(self.rowid, "values")
        self.vals: list[str] = list(vals)
        self.pulse_vals: list[str] = self.vals[self.column].split()

        self.option_var = {}
        self.checkbuttons = {}

        self.create_checkbuttons()

        # get screen width and height
        ws = self.root.winfo_screenwidth()  # width of the screen
        hs = self.root.winfo_screenheight()  # height of the screen

        # calculate x and y coordinates for the Tk root window
        x = (ws / 2) - (w / 2) + x / 2
        y = (hs / 2) - (h / 2) + y / 2

        # set the dimensions of the screen
        # and where it is placed
        self.root.geometry("%dx%d+%d+%d" % (w, h, x - 60, y))  # NOQA: UP031 The geometry call needs it specified in this way
        self.save_pulse_button = ttk.Button(
            self.root, text="Ok", command=self.on_return
        ).grid(
            column=gui_config.PULSEBLOCKS,
            row=0,
            padx=5,
            pady=5,
            columnspan=1,
            sticky="e",
        )

        self.root.protocol("WM_DELETE_WINDOW", self.abort)
        self.root.bind("<Escape>", lambda *ignore: self.destroy())

    def create_checkbuttons(self):
        for pulse in range(gui_config.PULSEBLOCKS):
            value = ncdcore.str2bool(str(self.pulse_vals[pulse]))
            if value is None:
                raise ValueError("Pulse value is None")
            else:
                var = tkinter.IntVar(value=int(value))

            self.option_var[pulse] = var

            CB = tkinter.Checkbutton(
                self.root,
                text=f"Pulse: {pulse}",
                variable=self.option_var[pulse],
                command=lambda pulse=pulse: self.toggle(pulse),
                onvalue=1,
                offvalue=0,
            )

            CB.grid(column=pulse, row=0, padx=5, pady=5, columnspan=1)

            self.option_var[pulse].set(1)

            self.checkbuttons[pulse] = CB

            if value == 1:
                self.checkbuttons[pulse].select()
            else:
                self.checkbuttons[pulse].deselect()

    def toggle(self, pulse):
        if self.option_var[pulse].get() == 1:
            self.option_var[pulse].set(1)
        else:
            self.option_var[pulse].set(0)

    def abort(self):
        self.root.destroy()
        del self

    def on_return(self):
        for pulse in range(gui_config.PULSEBLOCKS):
            val = str(self.option_var[pulse].get())
            self.pulse_vals[pulse] = val

        pulse_vals = " ".join(self.pulse_vals)

        self.vals[self.column] = pulse_vals

        self.parent.item(self.rowid, values=self.vals)
        self.root.destroy()
        del self


class EntryPopup(ttk.Entry):
    def __init__(self, parent, iid, column, text, entrytype=int, **kw):
        ttk.Style().configure("pad.TEntry", padding="1 1 1 1")
        super().__init__(parent, style="pad.TEntry", **kw)
        self.tv = parent
        self.iid = iid
        self.column = column
        self.entrytype = entrytype
        self.insert(0, text)
        self["exportselection"] = False

        self.focus_force()
        self.select_all()
        self.bind("<Return>", self.on_return)
        self.bind("<Control-a>", self.select_all)
        self.bind("<Escape>", lambda *ignore: self.destroy())

    def on_return(self, event):
        rowid = self.tv.focus()
        vals = self.tv.item(rowid, "values")
        vals = list(vals)

        if isinstance(self.entrytype, int):
            selection = round(float(self.get()))
        elif isinstance(self.entrytype, float):
            selection = float(self.get())
        elif isinstance(self.entrytype, list):
            selection = [str(int(f)) for f in self.get().split()]
            selection = " ".join(selection)
        else:
            selection = self.get()

        vals[self.column] = selection

        self.selection = selection

        self.tv.item(rowid, values=vals)
        self.destroy()

        self.tv.parent.parent.commit_config()
        self.tv.parent.profile.analyse_profile()
        self.tv.parent.generate_info_boxes()

    def select_all(self, *ignore):
        """Set selection on the whole text"""
        self.selection_range(0, "end")

        # returns 'break' to interrupt default key-bindings
        return "break"


class ProfileTab(ttk.Frame):
    def get_start_value(self):
        return self.clicked_start_trigger.get()

    def get_n_cycles_value(self):
        return int(self.n_cycles_entry_value.get())

    def delete_last_groups_button_action(self):
        row_int = len(self.profile.groups) - 1
        self.profile.delete_group(n=row_int)
        self.build_profile_tree()
        self.generate_info_boxes()

    def delete_group_button_action(self):
        rows = self.profile_config_tree.selection()

        if len(rows) == 0:
            messagebox.showinfo("Info", "Select a group to delete")

        for row in rows[::-1]:
            print(row)

            row_str = "0X" + (row.replace("I", ""))
            row_int = (int(row_str, 16)) - 1
            self.profile.delete_group(n=row_int)

            self.build_profile_tree()
            self.generate_info_boxes()

    def insert_group_button_action(self):
        try:
            row = self.profile_config_tree.selection()[0]
        except LookupError:
            messagebox.showinfo("Info", "A row must be selected to insert it before")

            return

        row_str = "0X" + (row.replace("I", ""))
        row_int = (int(row_str, 16)) - 1
        self.profile.insert_group(n=row_int, Group=group)
        self.build_profile_tree()
        self.generate_info_boxes()

    def append_group_button_action(self):
        self.profile.append_group(Group=group)
        self.build_profile_tree()
        self.generate_info_boxes()

    def build_profile_tree(self):
        COLUMN_NAMES = list(self.profile.groups[0].__dict__.keys())[0:8]
        COLUMN_NAMES = [f.replace("_", " ").title() for f in COLUMN_NAMES]
        COLUMN_NAMES.insert(0, "Group ID")  # Add Group ID as the first column

        if not hasattr(self, "profile_config_tree"):
            self.profile_config_tree = EditableTableview(
                self, columns=COLUMN_NAMES, show="headings"
            )
        else:
            del self.profile_config_tree
            self.profile_config_tree = EditableTableview(
                self, columns=COLUMN_NAMES, show="headings"
            )

        table_row = 5
        widths = [100, 100, 150, 150, 150, 150, 150, 150, 150]

        # add the columns headers
        for i, col in enumerate(COLUMN_NAMES):
            self.profile_config_tree.heading(i, text=col)
            self.profile_config_tree.column(
                i, minwidth=widths[i], width=widths[i], stretch=True, anchor="w"
            )

        # Insert sample data into the Treeview
        for i in range(len(self.profile.groups)):
            group_dict = self.profile.groups[i].__dict__
            group_list = list(group_dict.values())[0 : len(COLUMN_NAMES)]
            group_list.insert(0, i)
            self.profile_config_tree.insert("", "end", values=group_list)

        self.profile_config_tree.grid(
            column=0,
            row=table_row,
            padx=5,
            pady=5,
            columnspan=len(COLUMN_NAMES),
            rowspan=5,
        )

        verscrlbar = ttk.Scrollbar(
            self, orient="vertical", command=self.profile_config_tree.yview
        )

        verscrlbar.grid(
            column=len(widths),
            row=table_row,
            padx=0,
            pady=0,
            columnspan=1,
            rowspan=5,
            sticky="ns",
        )

        # Configuring treeview
        self.profile_config_tree.configure(yscrollcommand=verscrlbar.set)

        ############################################################

    def generate_info_boxes(self):
        try:
            self.total_frames_label.config(
                text=f"Total Frames: {self.profile.total_frames}"
            )
            self.total_time_per_cycle.config(
                text=f"Time/cycle: {self.profile.duration_per_cycle:.3f} s"
            )
            self.total_time_label.config(
                text=f"Total time: "
                f"{self.profile.duration_per_cycle * self.profile.cycles:.3f} s"
            )

        except Exception:
            #### total frames
            self.total_frames_label = ttk.Label(
                self, text=f"Total Frames: {self.profile.total_frames}"
            )
            self.total_frames_label.grid(column=8, row=1, padx=5, pady=5, sticky="e")

            self.total_time_per_cycle = ttk.Label(
                self, text=f"Time/cycle: {self.profile.duration_per_cycle:.3f} s"
            )
            self.total_time_per_cycle.grid(column=8, row=2, padx=5, pady=5, sticky="e")

            ### total time

            self.total_time_label = ttk.Label(
                self,
                text=f"Total time: "
                f"{self.profile.duration_per_cycle * self.profile.cycles:.3f} s",
            )
            self.total_time_label.grid(column=8, row=3, padx=5, pady=5, sticky="e")

    def edit_config_for_profile(self):
        group_list = []

        for _group_id, group_rowid in enumerate(
            self.profile_config_tree.get_children()
        ):
            group = self.profile_config_tree.item(group_rowid)["values"]

            wait_pulses = [int(f) for f in list(group[7].replace(" ", ""))]
            run_pulses = [int(f) for f in list(group[8].replace(" ", ""))]

            n_group = Group(
                frames=int(group[1]),
                wait_time=int(group[2]),
                wait_units=group[3],
                run_time=int(group[4]),
                run_units=group[5],
                pause_trigger=group[6],
                wait_pulses=wait_pulses,
                run_pulses=run_pulses,
            )

            group_list.append(n_group)

        cycles = self.get_n_cycles_value()
        profile_trigger = self.get_start_value()

        multiplier = [int(f.get()) for f in self.multiplier_var_options]

        new_profile = Profile(
            cycles=cycles,
            seq_trigger=profile_trigger,
            groups=group_list,
            multiplier=multiplier,
        )

        self.profile = new_profile
        self.configuration.profiles[self.n_profile] = new_profile

    def print_profile_button_action(self):
        self.parent.commit_config()
        self.profile.analyse_profile()
        self.generate_info_boxes()

        print(self.profile)

        for i in self.profile.groups:
            print(i)

    # TODO: https://github.com/DiamondLightSource/sas-bluesky/issues/23
    def build_multiplier_choices(self):
        self.multiplier_var_options = []

        ttk.Label(self, text="Multipliers:").grid(
            column=2, row=0, padx=5, pady=5, sticky="news"
        )

        for i in range(gui_config.PULSEBLOCKS):  # 4 pulse blocks
            col_pos = i + 3

            ttk.Label(self, text=f"{gui_config.PULSE_BLOCK_NAMES[i]}:").grid(
                column=col_pos, row=0, padx=5, pady=5, sticky="nsw"
            )

            self.multiplier_var = tkinter.StringVar(
                value=str(self.profile.multiplier[i])
            )
            tkinter.Entry(self, bd=1, width=10, textvariable=self.multiplier_var).grid(
                column=col_pos, row=0, padx=5, pady=5, sticky="nes"
            )

            self.multiplier_var_options.append(self.multiplier_var)

    def commit_and_plot(self):
        # self.edit_config_for_profile()
        self.parent.commit_config()

        ProfilePlotter(self.profile, gui_config.PULSE_BLOCK_NAMES)

    # def focus_out_generate_info_boxes(event):
    #     self.generate_info_boxes()

    def __init__(self, parent, notebook, configuration, n_profile):
        self.notebook = notebook
        self.parent = parent

        self.configuration = configuration
        self.n_profile = n_profile
        self.profile = self.configuration.profiles[self.n_profile]

        self.seq_table = self.profile.seq_table()

        super().__init__(self.notebook, borderwidth=5, relief="raised")

        self.notebook.add(self, text="Profile " + str(n_profile))

        self.columnconfigure(tuple(range(60)), weight=1)
        self.rowconfigure(tuple(range(30)), weight=1)

        ttk.Label(self, text="Profile " + str(n_profile)).grid(
            column=0, row=0, padx=5, pady=5, sticky="w"
        )

        self.outputs = self.profile.outputs()
        self.inputs = self.profile.inputs()

        if gui_config.USE_MULTIPLIERS:
            self.build_multiplier_choices()
            ### add tree view ############################################

        self.build_profile_tree()

        ############################################################

        ##### input trigger select

        self.seq_triggers = self.profile.seq_triggers()
        # self.seq_triggers = [f.lower() for f in self.seq_triggers]

        ttk.Label(self, text="Seq Trigger").grid(
            column=0, row=0, padx=5, pady=5, sticky="e"
        )

        self.clicked_start_trigger = tkinter.StringVar()
        ttk.OptionMenu(
            self,
            self.clicked_start_trigger,
            self.profile.seq_trigger,
            *self.seq_triggers,
        ).grid(column=1, row=0, padx=5, pady=5, sticky="w")

        ############# number of cycles box

        ttk.Label(self, text="No. of cycles").grid(
            column=0, row=1, padx=5, pady=5, sticky="e"
        )

        self.n_cycles_entry_value = tkinter.IntVar(self, value=self.profile.cycles)
        self.cycles_entry = tkinter.Entry(
            self, bd=1, width=15, textvariable=self.n_cycles_entry_value
        )

        self.cycles_entry.grid(column=1, row=1, padx=5, pady=5, sticky="w")

        # cycles_entry.bind("<FocusOut>", self.focus_out_generate_info_boxes)

        ############# plot button
        ############# profile info

        self.generate_info_boxes()

        ############profile settings
        self.plot_profile_button = ttk.Button(
            self, text="Plot Profile", command=self.commit_and_plot
        )

        self.insertrow_button = ttk.Button(
            self, text="Insert group", command=self.insert_group_button_action
        )

        self.deleterow_button = ttk.Button(
            self, text="Delete group", command=self.delete_group_button_action
        )

        self.appendrow_button = ttk.Button(
            self, text="Add group", command=self.append_group_button_action
        )

        self.deletefinalrow_button = ttk.Button(
            self, text="Discard group", command=self.delete_last_groups_button_action
        )

        self.print_profile_button = ttk.Button(
            self, text="Print Profile", command=self.print_profile_button_action
        )

        self.plot_profile_button.grid(
            column=8, row=0, padx=5, pady=5, columnspan=1, sticky="nes"
        )

        self.insertrow_button.grid(
            column=0, row=10, padx=5, pady=5, columnspan=1, sticky="news"
        )

        self.deleterow_button.grid(
            column=1, row=10, padx=5, pady=5, columnspan=1, sticky="news"
        )

        self.appendrow_button.grid(
            column=3, row=10, padx=5, pady=5, columnspan=1, sticky="news"
        )

        self.deletefinalrow_button.grid(
            column=4, row=10, padx=5, pady=5, columnspan=1, sticky="news"
        )

        self.print_profile_button.grid(
            column=3, row=1, padx=5, pady=5, columnspan=1, sticky="nes"
        )
