#!/dls/science/users/akz63626/i22/i22_venv/bin/python


"""

Python dataclasses and GUI as a replacement for NCDDetectors

"""

import json
import os
import tkinter
from tkinter import filedialog, messagebox, ttk
from tkinter.simpledialog import askstring

import matplotlib.pyplot as plt

from saxs_bluesky._version import __version__
from saxs_bluesky.gui.panda_gui_elements import ProfileTab
from saxs_bluesky.utils.beamline_client import BlueAPIPythonClient
from saxs_bluesky.utils.profile_groups import ExperimentLoader
from saxs_bluesky.utils.utils import (
    get_saxs_beamline,
    load_beamline_config,
)

############################################################################################

BL = get_saxs_beamline()
CONFIG = load_beamline_config()
DEFAULT_PROFILE = CONFIG.DEFAULT_PROFILE
############################################################################################


class PandAGUI(tkinter.Tk):
    def __init__(
        self,
        panda_config_yaml: str | None = None,
        configuration: ExperimentLoader | None = None,
        start: bool = True,
    ):
        self.panda_config_yaml = panda_config_yaml
        self.default_config_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "profile_yamls",
            "default_panda_config.yaml",
        )

        if (self.panda_config_yaml is None) and (configuration is None):
            self.configuration = ExperimentLoader.read_from_yaml(
                self.default_config_path
            )
        elif (self.panda_config_yaml is not None) and (configuration is None):
            self.configuration = ExperimentLoader.read_from_yaml(self.panda_config_yaml)
        elif (self.panda_config_yaml is None) and (configuration is not None):
            self.configuration = configuration
        else:
            print(
                "Must pass either panda_config_yaml or configuration object. Not both"
            )
            quit()

        self.instrument_session = str(
            askstring(
                "Instrument Session",
                "Enter an intrument session:",
                initialvalue=self.configuration.instrument_session,
            )
        )

        self.profiles = self.configuration.profiles

        self.window = tkinter.Tk()
        self.window.wm_resizable(True, True)
        self.window.minsize(600, 200)
        self.theme(CONFIG.THEME_NAME)

        menubar = tkinter.Menu(self.window)
        filemenu = tkinter.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.open_new_window)
        filemenu.add_command(label="Open", command=self.load_config)
        filemenu.add_command(label="Save", command=self.save_config)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.window.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        helpmenu = tkinter.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="Help Index", command=self.show_about)
        helpmenu.add_command(label="About...", command=self.show_about)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.window.config(menu=menubar)

        self.build_exp_run_frame()

        self.window.title("PandA Config")
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill="both", side="top", expand=True)

        for i in range(self.configuration.n_profiles):
            proftab_object = ProfileTab(self, self.notebook, self.configuration, i)
            # tab_names = self.notebook.tabs()
            # proftab_object: ProfileTab = self.notebook.nametowidget(tab_names[i])
            self.delete_profile_button = ttk.Button(
                proftab_object, text="Delete Profile", command=self.delete_profile_tab
            )

            self.delete_profile_button.grid(
                column=7, row=10, padx=5, pady=5, columnspan=1, sticky="news"
            )

        ########################################################
        self.build_exp_info_frame()
        ######## #settings and buttons that apply to all profiles
        self.build_global_settings_frame()

        self.build_pulse_frame()
        self.build_active_detectors_frame()

        self.build_add_frame()

        #################################################################

        blueapi_config_path = (
            f"./src/saxs_bluesky/blueapi_configs/{BL}_blueapi_config.yaml"
        )

        self.client = BlueAPIPythonClient(
            BL, blueapi_config_path, self.instrument_session
        )

        if start:
            self.window.mainloop()

    def open_new_window(self):
        PandAGUI()

    def show_about(self):
        messagebox.showinfo("About", __version__)

    def theme(self, theme_name: str):
        style = ttk.Style(self.window)
        print("All themes:", style.theme_names())
        style.theme_use(theme_name)

    def add_profile_tab(self, event):
        if self.notebook.select() == self.notebook.tabs()[-1]:
            print("new profile tab created")

            self.notebook.forget(self.add_frame)

            self.configuration.append_profile(DEFAULT_PROFILE)

            new_profile_tab = ProfileTab(
                self,
                self.notebook,
                self.configuration,
                len(self.configuration.profiles) - 1,
            )

            self.notebook.add(
                new_profile_tab, text=f"Profile {len(self.configuration.profiles) - 1}"
            )

            self.add_frame = tkinter.Frame()
            self.notebook.add(self.add_frame, text="+")
            self.window.bind("<<NotebookTabChanged>>", self.add_profile_tab)

            for n, _tab in enumerate(self.notebook.tabs()[0:-1]):
                self.notebook.tab(n, text="Profile " + str(n))

            self.delete_profile_button = ttk.Button(
                new_profile_tab, text="Delete Profile", command=self.delete_profile_tab
            )
            self.delete_profile_button.grid(
                column=7, row=10, padx=5, pady=5, columnspan=1, sticky="news"
            )

            self.notebook.select(self.notebook.tabs()[-2])

    def delete_profile_tab(self):
        answer = messagebox.askyesno(
            "Close Profile", "Delete this profile? Are you sure?"
        )

        if answer and (self.configuration.n_profiles >= 2):
            index_to_del = self.notebook.index("current")

            if index_to_del == 0:
                select_tab_index = 1
            else:
                select_tab_index = index_to_del - 1

            self.notebook.select(self.notebook.tabs()[select_tab_index])
            self.configuration.delete_profile(index_to_del)
            self.notebook.forget(self.notebook.tabs()[index_to_del])
        elif answer and (self.configuration.n_profiles == 1):
            messagebox.showinfo("Info", "Must have atleast one profile")

        tab_names = self.notebook.tabs()

        for n, _tab in enumerate(self.notebook.tabs()[0:-1]):
            self.notebook.tab(n, text="Profile " + str(n))
            proftab_object: ProfileTab = self.notebook.nametowidget(tab_names[n])
            ttk.Label(proftab_object, text="Profile " + str(n)).grid(
                column=0, row=0, padx=5, pady=5, sticky="w"
            )

        return None

    def commit_config(self):
        tab_names = self.notebook.tabs()

        for i in range(self.configuration.n_profiles):
            proftab_object: ProfileTab = self.notebook.nametowidget(tab_names[i])
            proftab_object.edit_config_for_profile()

    def load_config(self):
        panda_config_yaml = filedialog.askopenfilename()

        if (len(panda_config_yaml)) != 0:
            answer = messagebox.askyesno(
                "Close/Open New", "Finished editing this profile? Continue?"
            )

            if answer:
                self.window.destroy()
                PandAGUI(panda_config_yaml)
            else:
                return

    def save_config(self):
        panda_config_yaml = filedialog.asksaveasfile(
            mode="w", defaultextension=".yaml", filetypes=[("yaml", ".yaml")]
        )

        if panda_config_yaml:
            self.commit_config()
            self.configuration.save_to_yaml(panda_config_yaml.name)

            config_dict = self.configuration.to_dict()

            with open(panda_config_yaml.name.replace("yaml", "json"), "w") as fpo:
                json.dump(config_dict, fpo, indent=2)

    def open_textedit(self):
        if os.path.exists("/dls_sw/apps/atom/1.42.0/atom"):
            os.system(f"/dls_sw/apps/atom/1.42.0/atom {self.panda_config_yaml} &")
        else:
            try:
                os.system(f"subl {self.panda_config_yaml} &")
            except FileNotFoundError:
                os.system(f"gedit {self.panda_config_yaml} &")

    def show_wiring_config(self):
        fig, ax = plt.subplots(1, 1, figsize=(16, 8))

        labels = ["TTLIN", "LVDSIN", "TTLOUT", "LVDSOUT"]

        for key in CONFIG.TTLIN.keys():
            INDev = CONFIG.TTLIN[key]

            ax.scatter(0, key, color="k", s=50)
            ax.text(0 + 0.1, key, INDev)

        for key in CONFIG.LVDSIN.keys():
            LVDSINDev = CONFIG.LVDSIN[key]

            ax.scatter(1, key, color="k", s=50)
            ax.text(1 + 0.1, key, LVDSINDev)

        for key in CONFIG.TTLOUT.keys():
            TTLOUTDev = CONFIG.TTLOUT[key]

            ax.scatter(2, key, color="b", s=50)
            ax.text(2 + 0.1, key, TTLOUTDev)

        for key in CONFIG.LVDSOUT.keys():
            LVDSOUTDev = CONFIG.LVDSOUT[key]
            ax.scatter(3, key, color="b", s=50)
            ax.text(3 + 0.1, key, LVDSOUTDev)

        ax.set_ylabel("I/O Connections")
        ax.grid()
        ax.set_xlim(-0.2, 4)
        plt.gca().invert_yaxis()
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=90)
        plt.show()

    def get_plans(self):
        plans = self.client.get_plans().plans

        for plan in plans:
            print(plan.name, "\n")

    def get_devices(self):
        devices = self.client.get_devices().devices

        for dev in devices:
            print(dev, "\n\n")

    def configure_panda(self):
        self.commit_config()

        index = int(self.notebook.index("current"))

        profile_to_upload = self.configuration.profiles[index]
        # json_schema_profile = profile_to_upload.model_dump_json()

        params = {"profile": profile_to_upload}

        try:
            self.client.run("configure_panda_triggering", params)
        except ConnectionError:
            print("Could not upload profile to panda")

    def run_plan(self):
        # index = int(self.notebook.index("current"))
        # profile_to_upload = self.configuration.profiles[index]
        # json_schema_profile = profile_to_upload.model_dump_json()

        params = {
            "detectors": list(CONFIG.FAST_DETECTORS),
        }

        try:
            self.client.run("run_panda_triggering", params)
        except ConnectionError:
            print("Could not upload profile to panda")

    def set_detectors(self):
        params = {
            "bs_detectors": list(CONFIG.FAST_DETECTORS),
        }

        try:
            self.client.run("set_detectors", params)
        except ConnectionError:
            print("Could not upload profile to panda")

    def log_detectors(self):
        try:
            self.client.run("log_detectors", {})
        except ConnectionError:
            print("Could not upload profile to panda")

    def stop_plan(self):
        self.client.stop()

    def reload_environment(self):
        self.client.reload_environment()

    def pause_plan(self):
        self.client.pause()

    def resume_plan(self):
        self.client.resume()

    def build_exp_run_frame(self):
        self.run_frame = ttk.Frame(self.window, borderwidth=5, relief="raised")

        self.run_frame.pack(fill="both", expand=True, side="right")
        self.get_plans_button = ttk.Button(
            self.run_frame, text="Get Plans", command=self.get_plans
        ).grid(column=2, row=1, padx=5, pady=5, columnspan=1, sticky="news")

        self.get_devices_button = ttk.Button(
            self.run_frame, text="Get Devices", command=self.get_devices
        ).grid(column=2, row=3, padx=5, pady=5, columnspan=1, sticky="news")

        self.stop_plans_button = ttk.Button(
            self.run_frame, text="Stop Plan", command=self.stop_plan
        ).grid(column=2, row=5, padx=5, pady=5, columnspan=1, sticky="news")

        self.pause_plans_button = ttk.Button(
            self.run_frame, text="Pause Plan", command=self.pause_plan
        ).grid(column=2, row=7, padx=5, pady=5, columnspan=1, sticky="news")

        self.resume_plans_button = ttk.Button(
            self.run_frame, text="Resume Plan", command=self.resume_plan
        ).grid(
            column=2,
            row=9,
            padx=5,
            pady=5,
            columnspan=1,
            sticky="news",
        )

        self.run_plan_button = ttk.Button(
            self.run_frame, text="Run Plan", command=self.run_plan
        ).grid(column=2, row=11, padx=5, pady=5, columnspan=1, sticky="news")

        self.reload_env_button = ttk.Button(
            self.run_frame, text="Reload Env", command=self.reload_environment
        ).grid(column=2, row=12, padx=5, pady=5, columnspan=1, sticky="news")

        self.set_det_button = ttk.Button(
            self.run_frame, text="Set dets", command=self.set_detectors
        ).grid(column=2, row=13, padx=5, pady=5, columnspan=1, sticky="news")

        self.show_det_button = ttk.Button(
            self.run_frame, text="Log dets", command=self.log_detectors
        ).grid(column=2, row=14, padx=5, pady=5, columnspan=1, sticky="news")

    def build_global_settings_frame(self):
        self.global_settings_frame = ttk.Frame(
            self.window, borderwidth=5, relief="raised"
        )

        self.global_settings_frame.pack(fill="both", expand=True, side="bottom")

        # add a load/save/configure button
        self.load_button = ttk.Button(
            self.global_settings_frame, text="Load", command=self.load_config
        )

        self.save_button = ttk.Button(
            self.global_settings_frame, text="Save", command=self.save_config
        )

        self.configure_button = ttk.Button(
            self.global_settings_frame,
            text="Upload to PandA",
            command=self.configure_panda,
        )

        self.show_wiring_config_button = ttk.Button(
            self.global_settings_frame,
            text="Wiring config",
            command=self.show_wiring_config,
        )

        self.Opentextbutton = ttk.Button(
            self.global_settings_frame,
            text="Open Text Editor",
            command=self.open_textedit,
        )

        self.load_button.pack(fill="both", expand=True, side="left")
        self.save_button.pack(fill="both", expand=True, side="left")
        self.configure_button.pack(fill="both", expand=True, side="left")
        self.show_wiring_config_button.pack(fill="both", expand=True, side="left")
        self.Opentextbutton.pack(fill="both", expand=True, side="left")

    def build_add_frame(self):
        self.add_frame = tkinter.Frame()
        self.notebook.add(self.add_frame, text="+")
        self.window.bind("<<NotebookTabChanged>>", self.add_profile_tab)

    def build_exp_info_frame(self):
        self.experiment_settings_frame = ttk.Frame(
            self.window, borderwidth=5, relief="raised"
        )

        self.experiment_settings_frame.pack(
            fill="both", expand=True, side="bottom", anchor="w"
        )

        ttk.Label(
            self.experiment_settings_frame,
            text=f"Instrument: {BL}",
        ).grid(column=0, row=0, padx=5, pady=5, sticky="w")

        ttk.Label(
            self.experiment_settings_frame,
            text=f"Instrument Session: {self.instrument_session}",
        ).grid(column=0, row=1, padx=5, pady=5, sticky="w")

    def build_active_detectors_frame(self):
        self.active_detectors_checkbuttons = []

        for pulse in range(CONFIG.PULSEBLOCKS):
            active_detectors_frame_n = ttk.Frame(
                self.pulse_frame, borderwidth=5, relief="raised"
            )

            active_detectors_frame_n.pack(
                fill="both", expand=True, side="left", anchor="w"
            )

            Pulselabel = ttk.Label(
                active_detectors_frame_n, text=f"Pulse Group: {pulse + 1}"
            )

            Pulselabel.grid(column=0, row=0, padx=5, pady=5, sticky="w")

            # if pulse == 0:
            TTLLabel = ttk.Label(active_detectors_frame_n, text="TTL:")
            TTLLabel.grid(column=0, row=1, padx=5, pady=5, sticky="w")

            for n, det in enumerate(CONFIG.PULSE_CONNECTIONS[pulse + 1]):
                # experiment_var=tkinter.StringVar(value=self.configuration.experiment)

                if (det.lower() == "fs") or ("shutter" in det.lower()):
                    ad_entry = tkinter.Checkbutton(
                        active_detectors_frame_n, bd=1, text=det, state="disabled"
                    )
                    ad_entry.select()
                else:
                    ad_entry = tkinter.Checkbutton(
                        active_detectors_frame_n, bd=1, text=det
                    )

                ad_entry.grid(column=n + 1, row=1, padx=5, pady=5, sticky="w")

                self.active_detectors_checkbuttons.append(ad_entry)

    def build_pulse_frame(self):
        self.pulse_frame = ttk.Frame(self.window, borderwidth=5, relief="raised")
        self.pulse_frame.pack(fill="both", side="left", expand=True)
        Outlabel = ttk.Label(self.pulse_frame, text="Enable Device")
        Outlabel.pack(fill="both", side="top", expand=True)


if __name__ == "__main__":
    # Use the following url
    # https://github.com/DiamondLightSource/blueapi/blob/main/src/blueapi/client/client.py
    # blueapi -c i22_blueapi_config.yaml controller run count '{"detectors":["saxs"]}'

    # dir_path = os.path.dirname(os.path.realpath(__file__))
    # config_filepath = os.path.join(dir_path, "profile_yamls", "panda_config.yaml")
    PandAGUI(configuration=CONFIG.DEFAULT_EXPERIMENT)
