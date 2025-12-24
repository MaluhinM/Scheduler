# Scheduler - программа для управления расписанием уроков.
# Copyright (C) 2025 Малухин Мирон
#
# Это программное обеспечение распространяется под лицензией MIT.
# Подробнее см. в файле LICENSE.

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk, ImageSequence, ImageFont, ImageDraw
import imageio
from math import floor, ceil, sin, cos, pi
from random import randint, choice

import os
import sys
import shutil
from zipfile import ZipFile, BadZipFile
from pathlib import Path
import plistlib
from getpass import getuser
from glob import \
    glob as shitty_glob  # glob.glob() is shitty so I wrote my own glob() using glob.glob() lol 💀 (I'm dumb)
import ctypes
from pathvalidate import sanitize_filename

from tkcalendar import Calendar
import datetime
import calendar
import time
from ntplib import NTPClient, NTPException
from socket import gaierror

from threading import Thread

if sys.platform == 'win32':
    import winreg


__version__ = '2025.12.24'
__author__ = 'Malukhin Miron'


class Scheduler:
    WEEKNAMES = ('Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресение')
    WEEKNAMES2 = ('понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу', 'воскресение')
    WEEKNAMES3 = ('Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс')
    MONTHNAMES = ('Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь',
                  'Октябрь', 'Ноябрь', 'Декабрь')
    MONTHNAMES2 = ('Января', 'Февраля', 'Марта', 'Апреля', 'Мая', 'Июня', 'Июля', 'Августа', 'Сентября',
                   'Октября', 'Ноября', 'Декабря')

    def __init__(self):
        self.RESTART = False
        self.integrity_check(init=True)

        def configure_values(values, keys=None):
            if keys is None:
                keys = []
            for i, x in values.items():
                if isinstance(x, dict):
                    values[i] = configure_values(x, keys + [i])
                    return values
                config = values_config
                for j in keys:
                    config = config[j]
                values[i] = eval(config[i], {'self': self, 'x': x})
            return values

        for i in glob('Scheduler_Data/Temp/*'):
            if os.path.isdir(i):
                shutil.rmtree(i, ignore_errors=True)
            else:
                os.remove(i)

        if sys.platform == 'win32':
            fa = FileAssociation()
            if not fa.check_file_association('.scheduler-data'):
                fa.set_file_association('.scheduler-data', 'Scheduler', sys.argv[0],
                                        'Файл установки компонентов Scheduler')

        self.Scheduler_data = eval(open('Scheduler_Data/data/Scheduler_data.dat', 'r', encoding='utf-8').read())
        self.Values = eval(open('Scheduler_Data/data/default_values.dat', 'r', encoding='utf-8').read())
        values_config = eval(open('Scheduler_Data/data/values_config.dat', 'r', encoding='utf-8').read())
        self.Values = configure_values(self.Values)

        self.offset = self.Scheduler_data['offset']
        for font in glob(f'Scheduler_Data/Fonts/{self.Scheduler_data["font"]}/*.ttf'):
            response = FontManager.install_font(font)
            if response is False:
                return
        self.CURRENT_THEME = self.Scheduler_data['theme']
        # shutil.copy(f'Scheduler_Data/Fonts/{self.Scheduler_data["font"]}/{self.Scheduler_data["font"]}.dat',
        #             f'Scheduler_Data/data/fonts.dat')
        # shutil.copy(f'Scheduler_Data/FontSizes/{self.Scheduler_data["fontsize"]}.txt',
        #             f'Scheduler_Data/data/fontsize.dat')
        # shutil.copy(f'Scheduler_Data/Themes/{self.CURRENT_THEME}.txt', f'Scheduler_Data/data/colors.dat')
        self.update_colors()

        resizable = self.Scheduler_data['root_resizable'], self.Scheduler_data['root_resizable']
        self.root = WindowManager.CreateWindow(
            title=f'Scheduler - Расписание - {self.Scheduler_data["current_schedule"]}',
            bg=self.Colors['lessons_frame_bg'], resizable=resizable, attrs={'-alpha': 0})

        self.update_fonts()
        self.update_style()
        self.customStyle.theme_use(self.CURRENT_THEME)
        shutil.copy(f'Scheduler_Data/Themes/{self.CURRENT_THEME}.txt', f'Scheduler_Data/data/colors.dat')
        self.update_colors()

        self.initialize = WindowManager.CreateWindow(self.root, 'Scheduler - Инициализация', bg=self.Colors['extra'],
                                                     switch_fullscreen=False, switch_topmost=False,
                                                     attrs={'-alpha': 0, '-topmost': True})
        WindowManager.SetToCenter(self.initialize)

        while True:
            result = self.get_schedule()
            if result == -1:
                continue
            if result[0] is True:
                self.Scheduler_data['current_schedule'] = result[1]
                open('Scheduler_Data/data/Scheduler_data.dat', 'w', encoding='utf-8').write(str(self.Scheduler_data))
                self.root.mainloop()
                return
            break

        empty = tk.Label(self.initialize, bg=self.Colors['extra'])
        empty.pack()
        self.update_animation(self.Scheduler_data['animation'])
        animation = self.RunAnimation(self.initialize)
        animation.start()

        self.loadlabel = tk.Label(self.initialize, text='Загрузка...',
                                  bg=self.Colors['extra'], fg=self.Colors['title1'],
                                  font=self.Fonts['huge_title'])
        self.loadlabel.pack(padx=30, pady=20)
        self.initialize.attributes('-alpha', 1)

        # Запускаем инициализацию в отдельном потоке
        thread = Thread(target=self._init_background, daemon=True)
        thread.start()
        self.root.mainloop()

        # Продолжаем выполнение после инициализации
        self.initialize.destroy()
        del self.initialize

        self.root.bind('<space>', lambda event: self.PackBackpack())
        self.root.bind('<Return>', lambda event: self.PackBackpack())
        self.root.mainloop()

    def _init_background(self):
        def check_scrollable():
            if self.subjects_length == 0:
                return None
            if self.scheduleframe.winfo_height() > self.canvas.winfo_height():
                self.scrollbar.configure(command=self.canvas.yview)
                self.root.bind('<MouseWheel>', lambda event: WindowManager.on_mousewheel(event, self.canvas))
                self.root.bind('<Up>', lambda event: self.canvas.yview_scroll(-2, 'units'))
                self.root.bind('<Down>', lambda event: self.canvas.yview_scroll(2, 'units'))
                return True
            else:
                self.scrollbar.configure(command=lambda *args: None)
                self.root.bind('<MouseWheel>', lambda event: None)
                self.root.bind('<Up>', lambda event: None)
                self.root.bind('<Down>', lambda event: None)
                return False

        def check_size(event=None):
            self.root_width = self.root.winfo_width()
            self.lessonframewidth = self.root_width - self.INDENTATION

            btn.configure('out', master_kwargs={'width': self.root_width})
            try:
                for i, j in self.widgets:
                    i.configure(width=self.lessonframewidth)
                    j.configure(width=self.lessonframewidth)
            except tk.TclError:
                pass
            if hasattr(self, 'CHECK_SIZE_AFTER'):
                self.root.after_cancel(self.CHECK_SIZE_AFTER)
                del self.CHECK_SIZE_AFTER

                try:
                    check_scrollable()
                except tk.TclError:
                    pass

            self.CHECK_SIZE_AFTER = self.root.after(100, lambda: self.check_time(loop=False))

        def _quit(event=None):
            if self.root.state() == 'normal' and not self.root.attributes('-fullscreen'):
                width, height = self.root.winfo_width(), self.root.winfo_height()
                open('Scheduler_Data/data/window_size.dat', 'w', encoding='utf-8').write(f'({width}, {height})')
            self.root.destroy()

        # Все долгие операции выполняются здесь
        self.USE_TIME_SERVER = self.Scheduler_data['use_time_server']
        if self.USE_TIME_SERVER:
            self.TIME_CLIENT = NTPClient()
            self.TIME_SYNC_INTERVAL = self.Scheduler_data['time_sync_interval']

        self.images = {
            i.replace('Scheduler_Data/images/', '').replace('.png', ''): tk.PhotoImage(file=i, master=self.root) for i
            in glob('Scheduler_Data/images/*.png')}
        self.get_time_now(init=True)

        if randint(1, 5) == 1 and self.Scheduler_data['animation'] == ['GIFPlayer',
                                                                       'winload'] and sys.platform == 'win32':
            text = 'Завершение работы'
            img = None
        else:
            text = eval(open('Scheduler_Data/data/welcome_text.dat', 'r', encoding='utf-8').read())
            text[1].append(f'Шанс увидеть эту надпись: {round(100 / (len(text) * (len(text[1]) + 1)), 2)}%')
            images = ('night', 'morning', 'day', 'evening')
            pick = randint(0, len(text) - 1)
            if self.getdatetime('0:00') <= self.now < self.getdatetime('6:00'):
                index = 0
            elif self.getdatetime('6:00') <= self.now < self.getdatetime('12:00'):
                index = 1
            elif self.getdatetime('12:00') <= self.now < self.getdatetime('18:00'):
                index = 2
            else:
                index = 3
            img = self.images[images[index]]
            if pick == 0:
                text = f' {text[pick][index]}'
            else:
                text = f' {choice(text[pick])}'

        self.loadlabel.destroy()
        tk.Label(self.initialize, text=text, image=img, compound='left',
                 bg=self.Colors['extra'], fg=self.Colors['title1'],
                 font=self.Fonts['huge_title']).pack(padx=10, pady=10)
        WindowManager.SetToCenter(self.initialize)
        self.initialize.update()
        self.initialize.focus_force()

        self.IN_SLEEP = [False, True]

        self.ROUND_TIME_FUNCTION = ceil if self.Scheduler_data['ceil_time'] else floor
        self.ScrollbarWidth = 24
        self.INDENTATION = 10 + self.ScrollbarWidth
        widthmax, heightmax = 720 + self.ScrollbarWidth, 732
        self.lessonframewidth = widthmax - self.INDENTATION
        self.lessonframeheight = 80

        self.width, self.height = widthmax, heightmax
        self.root.minsize(widthmax, heightmax)
        width, height = eval(open('Scheduler_Data/data/window_size.dat', 'r', encoding='utf-8').read())
        WindowManager.FixWindowSize(self.root, width, height)

        btn = CreateButton(
            self.root, 'Собрать рюкзак', self.PackBackpack,
            default_kwargs={'bg': self.Colors['extra'], 'fg': self.Colors['title1'], 'r': 8, 'bd': 2, 'bdr': 10,
                            'bdcolor': self.Colors['shade2']},
            target_kwargs={'bg': self.Colors['shade2'], 'fg': self.Colors['title1'], 'offset': 0, 'bd': 2,
                           'bdcolor': self.Colors['shade2']},
            master_kwargs={'font': self.Fonts['bigger_title'], 'text_align': 'center',
                           'place': {'method': 'pack', 'side': 'bottom', 'fill': 'x', 'expand': False}},
            animation_kwargs=self.Values['animation_kwargs'],
        )

        self.new_view = False
        self.set_view(0)
        self.load_schedule(ShowLoadingAnimation=False, init=True)

        check_size()
        check_scrollable()
        self.root.bind('<Configure>', check_size)
        self.root.protocol('WM_DELETE_WINDOW', _quit)
        self.root.bind('<Escape>', _quit)
        for i in range(10):
            self.root.bind(str(i), lambda event, num=i: self.view_lesson_info(None, self.root, num))

        if self.Scheduler_data['set_in_sleep']:
            self.root.bind('<FocusIn>', self.set_in_sleep)
            self.root.bind('<FocusOut>', self.set_in_sleep)
        else:
            self.set_in_sleep('<FocusIn event>')

        WindowManager.SetToCenter(self.root)
        self.root.update()
        self.root.attributes('-alpha', 1)
        self.root.focus_force()

        self.root.quit()

    def integrity_check(self, master=None, showinfo=False, init=False):
        def stop(event=None):
            sys.exit(1)

        def quit(event=None):
            self.checker.quit()
            self.checker.destroy()
            if master:
                master.deiconify()

        def check_corruption(file):
            try:
                exec(open(file, 'r', encoding='utf-8').read(), {**globals(), 'self': self})
                return False
            except:
                return True

        def add_to_corrupted(file):
            dirname = os.path.dirname(file)
            basename = os.path.basename(file)
            if dirname in corrupted and basename not in corrupted[dirname]:
                corrupted[dirname].append(basename)
            else:
                corrupted[dirname] = [basename]

        def create_sector(title, items, file_text, folder_text, image, bg):
            tk.Label(infoframe, text=title, font=font2, bg=mainbg, fg=fg).pack(anchor='w', padx=pad1)
            for i, j in items:
                if len(j) > 0:
                    path = i
                    if i == '':
                        i = 'Корневая папка'
                    pathframe = tk.Frame(infoframe, bg=mainbg, bd=0)
                    pathframe.pack(anchor='w', pady=pad3)
                    tk.Label(pathframe, text=i.replace('/', '\\'), font=font1, bg=mainbg, fg=fg).pack(anchor='w',
                                                                                                      padx=pad2)
                    for k in j:
                        if '.' in k:
                            msg = file_message.format(
                                main_text=file_text,
                                filename=k,
                                filetype=get_file_type_description(k),
                                location=os.path.abspath(path)
                            )
                        else:
                            msg = folder_message.format(
                                main_text=folder_text,
                                filename=k,
                                location=os.path.abspath(path)
                            )

                        sectorframe = tk.Frame(pathframe, bg=mainbg, bd=0)
                        sectorframe.pack()
                        sectorcanvas = CreateButton(
                            sectorframe, k,
                            default_kwargs={'bg': mainbg, 'fg': fg, 'r': 10, 'bdr': 12, 'bd': 2, 'bdcolor': bg},
                            target_kwargs={'bg': extrabg, 'fg': fg, 'bd': 3, 'bdcolor': bg},
                            master_kwargs={'font': font1, 'image': image, 'width': 1000, 'padx': 25, 'pady': 2,
                                           'ipady': 10,
                                           'place': {'method': 'pack', 'side': 'bottom', 'fill': 'x', 'expand': False}},
                            animation_kwargs=animation_kwargs
                        )
                        ToolTip(
                            sectorframe,
                            msg=msg,
                            delay=20, background=extrabg, foreground=fg,
                            parent_kwargs={'master': sectorcanvas.canvas, 'bg': bg},
                            font=font3
                        )

        def add_to_all_requirements(paths):
            for i in paths:
                files = glob(f'{i}/*')
                for j in files:
                    all_requirements[i].append(os.path.basename(j))
                    if os.path.isdir(j):
                        add_to_all_requirements([j])

        def find_corruption(data, requirements, check_type=True):
            for i, j in requirements.items():
                if i not in data:
                    return True
                if isinstance(j, dict):
                    return find_corruption(data[i], j, check_type)
                if check_type and not isinstance(data[i], eval(j)):
                    return True
            return False

        if init:
            animation_kwargs = {}
        else:
            animation_kwargs = self.Values['animation_kwargs']

        if os.path.exists('requirements.ini'):
            requirements = eval(open('requirements.ini', 'r', encoding='utf-8').read())
            main_requirements = requirements['main']
            additional_paths = requirements['additional']
            data_requirements = requirements['data']
            values_requirements = requirements['values']
            presets_requirements = requirements['presets']
            fonts_requirements = requirements['fonts']
            ignore = requirements['ignore']
            missing = {}

            for i, j in main_requirements.items():
                miss = []
                for k in j:
                    element = os.path.join(i, k).replace('\\', '/')
                    if element in ignore:
                        continue
                    if not os.path.exists(element):
                        miss.append(k)
                missing[i.replace('\\', '/')] = miss
        else:
            main_requirements = {
                '': ['requirements.ini']
            }
            additional_paths = []
            data_requirements = {}
            presets_requirements = {}
            fonts_requirements = []
            ignore = []
            missing = {
                'Scheduler_Data/data': []
            }

        if 'colors.dat' not in missing['Scheduler_Data/data'] and not check_corruption(
                'Scheduler_Data/data/colors.dat'):
            self.update_colors()
            fg = self.Colors['title1']
            mainbg = self.Colors['main']
            extrabg = self.Colors['extra']
            color1 = self.Colors['color1']
            color1a = self.Colors['color1a']
            color2 = self.Colors['color2']
            color2a = self.Colors['color2a']
            color3 = self.Colors['color3']
            color3a = self.Colors['color3a']
            color4 = self.Colors['color4']
            color4a = self.Colors['color4a']
        else:
            fg = 'white'
            mainbg = 'black'
            extrabg = 'black'
            color1 = 'green'
            color1a = 'green'
            color2 = 'cyan'
            color2a = 'cyan'
            color3 = 'orange'
            color3a = 'orange'
            color4 = 'red'
            color4a = 'red'

        if os.path.exists('requirements.ini'):
            corrupted = {}

            for i in glob('**', recursive=True):
                if any(i.startswith(j) for j in ignore):
                    continue
                if i.split('.')[-1] in ('dat', 'ini'):
                    if check_corruption(i):
                        add_to_corrupted(i)

            for i in glob('Scheduler_Data/Schedules/*.txt'):
                if not check_corruption(i):
                    data = eval(open(i, 'r', encoding='utf-8').read())
                    if 'subjects' not in data:
                        add_to_corrupted(i)
                        continue
                    if 'duration' not in data:
                        add_to_corrupted(i)
                        continue
                    if 'startfrom' not in data:
                        add_to_corrupted(i)
                        continue

                    subjects = data['subjects']
                    sub_length = len(subjects)
                    if sub_length != 7:
                        add_to_corrupted(i)
                        continue

                    duration = data['duration']
                    dur_length = len(duration)
                    if dur_length != 7:
                        add_to_corrupted(i)
                        continue

                    startfrom = data['startfrom']
                    startfrom_length = len(startfrom)
                    if startfrom_length != 7:
                        add_to_corrupted(i)
                        continue

                    for j in range(7):
                        sub_length = len(subjects[j])
                        if sub_length > 9:
                            add_to_corrupted(i)
                            continue
                        dur_length = len(duration[j])
                        if dur_length > 9:
                            add_to_corrupted(i)
                            continue
                        if sub_length != dur_length:
                            add_to_corrupted(i)
                            continue
                        if not isinstance(startfrom[j], int):
                            add_to_corrupted(i)
                            continue

            for i in glob('Scheduler_Data/Animations/presets/*.txt'):
                if not check_corruption(i):
                    data = eval(open(i, 'r', encoding='utf-8').read())
                    if find_corruption(data, presets_requirements):
                        add_to_corrupted(i)

            for i in glob('Scheduler_Data/Fonts/*'):
                file = f'{os.path.basename(i)}.dat'

                if not os.path.isdir(i):
                    add_to_corrupted(i)
                elif not os.path.exists(f'{i}/{file}'):
                    if i not in missing:
                        missing[i] = []
                    missing[i].append(file)
                elif not check_corruption(f'{i}/{file}'):
                    data = eval(open(f'{i}/{file}', 'r', encoding='utf-8').read())
                    for key in fonts_requirements:
                        if key not in data:
                            add_to_corrupted(f'{i}/{file}')
                            break

            for i in glob('Scheduler_Data/FontSizes/*.txt'):
                if not check_corruption(i):
                    data = eval(open(i, 'r', encoding='utf-8').read())
                    for key in fonts_requirements:
                        if key not in data:
                            add_to_corrupted(i)
                            break

            fonts_corrupted = check_corruption('Scheduler_Data/data/fonts.dat')
            fontsize_corrupted = check_corruption('Scheduler_Data/data/fontsize.dat')
            if 'fonts.dat' not in missing['Scheduler_Data/data'] and not fonts_corrupted and 'fontsize.dat' not in \
                    missing['Scheduler_Data/data'] and not fontsize_corrupted:
                data1 = eval(open('Scheduler_Data/data/fonts.dat', 'r', encoding='utf-8').read())
                data2 = eval(open('Scheduler_Data/data/fontsize.dat', 'r', encoding='utf-8').read())
                for i in data1.keys():
                    if i not in data2:
                        add_to_corrupted('Scheduler_Data/data/fonts.dat')
                        add_to_corrupted('Scheduler_Data/data/fontsize.dat')
                        break

            if 'images_config.dat' not in missing['Scheduler_Data/data'] and not check_corruption(
                    'Scheduler_Data/data/images_config.dat'):
                data = eval(open('Scheduler_Data/data/images_config.dat', 'r', encoding='utf-8').read())
                for i in data.keys():
                    if i not in missing['Scheduler_Data/images'] and not os.path.exists(f'Scheduler_Data/images/{i}'):
                        add_to_corrupted('Scheduler_Data/data/images_config.dat')
                        break

            if 'Scheduler_data.dat' not in missing['Scheduler_Data/data'] and not check_corruption(
                    'Scheduler_Data/data/Scheduler_data.dat'):
                data = eval(open('Scheduler_Data/data/Scheduler_data.dat', 'r', encoding='utf-8').read())
                if find_corruption(data, data_requirements):
                    add_to_corrupted('Scheduler_Data/data/Scheduler_data.dat')
                else:
                    if f"Scheduler_Data/Fonts/{data['font']}" not in glob('Scheduler_Data/Fonts/*') and 'Fonts' not in \
                            missing['Scheduler_Data']:
                        add_to_corrupted('Scheduler_Data/data/Scheduler_data.dat')
                    elif f"Scheduler_Data/FontSizes/{data['fontsize']}.txt" not in glob(
                            'Scheduler_Data/FontSizes/*.txt') and 'FontSizes' not in missing['Scheduler_Data']:
                        add_to_corrupted('Scheduler_Data/data/Scheduler_data.dat')
                    elif f"Scheduler_Data/Themes/{data['theme']}.txt" not in glob(
                            'Scheduler_Data/Themes/*.txt') and 'Themes' not in missing['Scheduler_Data']:
                        add_to_corrupted('Scheduler_Data/data/Scheduler_data.dat')
                    else:
                        offset = data['offset']
                        if 'seconds' not in offset or 'minutes' not in offset or 'hours' not in offset:
                            add_to_corrupted('Scheduler_Data/data/Scheduler_data.dat')
                        elif not isinstance(offset['seconds'], int) or not isinstance(offset['minutes'],
                                                                                      int) or not isinstance(
                                offset['hours'], int):
                            add_to_corrupted('Scheduler_Data/data/Scheduler_data.dat')
                        else:
                            animation = data['animation']
                            for i in animation:
                                if not isinstance(i, str):
                                    add_to_corrupted('Scheduler_Data/data/Scheduler_data.dat')
                            if len(animation) == 0:
                                add_to_corrupted('Scheduler_Data/data/Scheduler_data.dat')
                            elif len(animation) == 1 and animation[0] in ('Handle', 'GIFPlayer'):
                                add_to_corrupted('Scheduler_Data/data/Scheduler_data.dat')
                            elif 'Animations' in missing['Scheduler_Data'] or 'scripts' in missing[
                                'Scheduler_Data/Animations']:
                                pass
                            elif f'Scheduler_Data/Animations/scripts/{animation[0]}.dat' not in glob(
                                    'Scheduler_Data/Animations/scripts/*.dat') and f'{animation[0]}.dat' not in missing[
                                'Scheduler_Data/Animations/scripts']:
                                add_to_corrupted('Scheduler_Data/data/Scheduler_data.dat')
                            elif 'presets' in missing['Scheduler_Data/Animations'] or 'GIFs' in missing[
                                'Scheduler_Data/Animations']:
                                pass
                            elif len(animation) > 1 and (
                                    f'Scheduler_Data/Animations/presets/{animation[1]}.txt' not in glob(
                                    'Scheduler_Data/Animations/presets/*.txt')
                                    and f'Scheduler_Data/Animations/GIFs/{animation[1]}.gif' not in glob(
                                'Scheduler_Data/Animations/GIFs/*.gif')):
                                add_to_corrupted('Scheduler_Data/data/Scheduler_data.dat')

            if 'default_values.dat' not in missing['Scheduler_Data/data'] and not check_corruption(
                    'Scheduler_Data/data/default_values.dat'):
                data = eval(open('Scheduler_Data/data/default_values.dat', 'r', encoding='utf-8').read())
                if find_corruption(data, values_requirements):
                    add_to_corrupted('Scheduler_Data/data/default_values.dat')

            if 'values_config.dat' not in missing['Scheduler_Data/data'] and not check_corruption(
                    'Scheduler_Data/data/values_config.dat'):
                data = eval(open('Scheduler_Data/data/values_config.dat', 'r', encoding='utf-8').read())
                if find_corruption(data, values_requirements, check_type=False):
                    add_to_corrupted('Scheduler_Data/data/default_values.dat')

            if 'welcome_text.dat' not in missing['Scheduler_Data/data'] and not check_corruption(
                    'Scheduler_Data/data/welcome_text.dat'):
                data = eval(open('Scheduler_Data/data/welcome_text.dat', 'r', encoding='utf-8').read())
                if not isinstance(data, tuple):
                    add_to_corrupted('Scheduler_Data/data/welcome_text.dat')
                elif len(data) != 2:
                    add_to_corrupted('Scheduler_Data/data/welcome_text.dat')
                elif len(data[0]) != 4:
                    add_to_corrupted('Scheduler_Data/data/welcome_text.dat')
        else:
            missing = {
                '': ['requirements.ini']
            }
            corrupted = {}
            fonts_corrupted = True
            fontsize_corrupted = True

        missing_val = missing.values()
        corrupted_val = corrupted.values()
        missing_amount = sum(map(len, missing_val))
        corrupted_amount = sum(map(len, corrupted_val))
        length = missing_amount + corrupted_amount

        temp_requirements = {}
        for i in glob('Scheduler_Data/Fonts/*'):
            temp_requirements[i] = []
        for i, j in main_requirements.items():
            temp_requirements[i] = j
        sorted_requirements = sorted(temp_requirements)
        all_requirements = {i: temp_requirements[i] for i in sorted_requirements}
        add_to_all_requirements(additional_paths)

        valid = {}
        for i, k in all_requirements.items():
            valid[i] = []
            for l in k:
                if (i not in missing or l not in missing[i]) and (i not in corrupted or l not in corrupted[i]):
                    valid[i].append(l)
        valid_amount = sum(map(len, valid.values()))

        if showinfo or any(missing_val) or any(corrupted_val):
            self.checker = WindowManager.CreateWindow(master, bg=mainbg, attrs={'-alpha': 0})
            if length == 0:
                self.checker.protocol('WM_DELETE_WINDOW', quit)
                self.checker.bind('<space>', quit)
                self.checker.bind('<Return>', quit)
                self.checker.bind('<Escape>', quit)
            else:
                self.checker.protocol('WM_DELETE_WINDOW', stop)
                self.checker.bind('<space>', stop)
                self.checker.bind('<Return>', stop)
                self.checker.bind('<Escape>', stop)
            if master:
                master.withdraw()

            if 'Scheduler_Data/data' in missing:
                missing_data = missing['Scheduler_Data/data']
            else:
                missing_data = []
            if 'Scheduler_Data/data' in corrupted:
                corrupted_data = corrupted['Scheduler_Data/data']
            else:
                corrupted_data = []
            bad_data = missing_data + corrupted_data
            if 'fonts.dat' not in bad_data and not fonts_corrupted and 'fontsize.dat' not in bad_data and not fontsize_corrupted:
                self.update_fonts(master=self.checker)
                font1 = self.Fonts['small_title']
                font2 = self.Fonts['bigger_title']
                font3 = self.Fonts['text']
            else:
                font1 = 'Arial 16'
                font2 = 'Arial 20 bold'
                font3 = 'Arial 10'

            if 'Scheduler_Data/data' in missing and 'tkinterstyle.dat' not in missing[
                'Scheduler_Data/data'] and not check_corruption(
                    'Scheduler_Data/data/tkinterstyle.dat') and 'Scheduler_data.dat' not in missing[
                'Scheduler_Data/data'] and not check_corruption(
                'Scheduler_Data/data/Scheduler_data.dat') and 'Scheduler_Data' in missing and 'Themes' not in missing[
                'Scheduler_Data']:
                self.update_style()
                data = eval(open('Scheduler_Data/data/Scheduler_data.dat', 'r', encoding='utf-8').read())
                current_theme = data['theme']
                shutil.copy(f'Scheduler_Data/Themes/{current_theme}.txt', 'Scheduler_Data/data/colors.dat')
                self.customStyle.theme_use(current_theme)

            if 'Scheduler_Data/images' in missing and 'check.png' not in missing['Scheduler_Data/images']:
                validimg = ImageTk.PhotoImage(Image.open('Scheduler_Data/images/check.png'))
            else:
                validimg = None
            if 'Scheduler_Data/images' in missing and 'close.png' not in missing['Scheduler_Data/images']:
                missimg = ImageTk.PhotoImage(Image.open('Scheduler_Data/images/close.png'))
            else:
                missimg = None
            if 'Scheduler_Data/images' in missing and 'broken.png' not in missing['Scheduler_Data/images']:
                corruptimg = ImageTk.PhotoImage(Image.open('Scheduler_Data/images/broken.png'))
            else:
                corruptimg = None

            if length == 0:
                title1 = 'Всё в порядке!'
            elif length == 1:
                title1 = 'Обнаружена неисправность'
            else:
                part1 = declination(length, ('Обнаружена', 'Обнаружено', 'Обнаружено'))
                part2 = declination(length, ('неисправность', 'неисправности', 'неисправностей'))
                title1 = f'{part1} {length} {part2}'

            if length == 0:
                title2 = 'Мастер проверки целостности программы не обнаружил ошибок.\nВсё в порядке!'
                msg = 'Мы проверили все необходимые для работы программы файлы и папки и не обнаружили проблем!'
                outline = color1a
                infoimage = validimg
            else:
                parts = []
                if missing_amount > 0:
                    part1 = declination(missing_amount,
                                        ('отсутствующий элемент', 'отсутствующих элемента', 'отсутствующих элементов'))
                    parts.append(f'{missing_amount} {part1}')
                if corrupted_amount > 0:
                    part2 = declination(corrupted_amount,
                                        ('повреждённый файл', 'повреждённых файла', 'повреждённых файлов'))
                    parts.append(f'{corrupted_amount} {part2}')
                text = ' и '.join(parts)

                if init:
                    title2 = f'Мастер проверки целостности программы остановил загрузку, так как обнаружил\n{text}'
                else:
                    title2 = f'Мастер проверки целостности программы обнаружил\n{text}'
                msg = 'Мы проверили все необходимые для работы программы файлы и папки и обнаружили несоответствия требованиям'
                outline = color4a
                infoimage = missimg

            self.checker.title(f'Scheduler - {title1}')

            container = tk.Frame(self.checker, bd=0, bg=mainbg)
            canvas = tk.Canvas(container, highlightthickness=0, bg=mainbg, width=1000, height=800)
            scrollbar = ttk.Scrollbar(container, orient='vertical')
            scrollbar.configure(command=canvas.yview)
            infoframe = tk.Frame(canvas, bg=mainbg, bd=0)

            infoframe.bind(
                '<Configure>',
                lambda e: canvas.configure(
                    scrollregion=canvas.bbox('all')
                )
            )

            canvas.create_window((0, 0), window=infoframe, anchor='nw')
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.yview_moveto(0)

            container.pack(fill='both', expand=True)
            canvas.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            self.checker.update()
            pad1 = 5
            pad2 = 25
            pad3 = 10

            info = tk.Frame(infoframe, bg=mainbg, bd=0)
            info.pack()
            infocanvas = CreateButton(
                info, title2,
                default_kwargs={'bg': mainbg, 'fg': fg, 'r': 10, 'bdr': 12, 'bd': 2, 'bdcolor': outline},
                target_kwargs={'bg': extrabg, 'fg': fg, 'bd': 3, 'bdcolor': outline},
                master_kwargs={'font': font1, 'image': infoimage, 'width': 1000, 'padx': 2, 'pady': 2,
                               'ipady': 30,
                               'place': {'method': 'pack', 'side': 'bottom', 'fill': 'x', 'expand': False}},
                animation_kwargs=animation_kwargs
            )
            ToolTip(
                info,
                msg=msg,
                delay=20, background=extrabg, foreground=fg,
                parent_kwargs={'master': infocanvas.canvas, 'bg': outline},
                font=font3
            )

            self.checker.bind('<MouseWheel>', lambda event: WindowManager.on_mousewheel(event, canvas))
            self.checker.bind('<Up>', lambda event: canvas.yview_scroll(-2, 'units'))
            self.checker.bind('<Down>', lambda event: canvas.yview_scroll(2, 'units'))

            file_message = '{main_text}\n\nИмя: {filename}\nТип: {filetype}\nРасположение: {location}'
            folder_message = '{main_text}\n\nИмя: {filename}\nТип: Папка с файлами\nРасположение: {location}'

            if missing_amount > 0:
                create_sector(
                    title=f'Отсутствующие элементы ({missing_amount}):',
                    items=missing.items(),
                    file_text='Мы не смогли найти этот файл',
                    folder_text='Мы не смогли найти эту папку',
                    image=missimg,
                    bg=color4a
                )

            if corrupted_amount > 0:
                create_sector(
                    title=f'Повреждённые элементы ({corrupted_amount}):',
                    items=corrupted.items(),
                    file_text='Местоположение или содержимое этого файла не совпадает с необходимыми требованиями',
                    folder_text='Местоположение или содержимое этой папки не совпадает с необходимыми требованиями',
                    image=corruptimg,
                    bg=color3a
                )

            if valid_amount > 0:
                create_sector(
                    title=f'Валидные элементы ({valid_amount}):',
                    items=valid.items(),
                    file_text='С этим файлом всё в порядке!',
                    folder_text='С этой папкой всё в порядке!',
                    image=validimg,
                    bg=color1a
                )

            window_width = self.checker.winfo_width()
            if length == 0:
                CreateButton(
                    self.checker, 'Отлично!', quit,
                    default_kwargs={'bg': color1, 'fg': fg, 'r': 8, 'bd': 2, 'bdr': 10, 'bdcolor': color1a},
                    target_kwargs={'bg': color1a, 'fg': fg, 'offset': 0, 'bd': 2, 'bdcolor': color1a},
                    master_kwargs={'font': font2, 'width': window_width, 'text_align': 'center',
                                   'place': {'method': 'pack', 'side': 'bottom', 'fill': 'x', 'expand': False}},
                    animation_kwargs=animation_kwargs,
                )
            else:
                if showinfo:
                    CreateButton(
                        self.checker, 'Это не я, оно само!', quit,
                        default_kwargs={'bg': color3, 'fg': fg, 'r': 8, 'bd': 2, 'bdr': 10, 'bdcolor': color3a},
                        target_kwargs={'bg': color3a, 'fg': fg, 'offset': 0, 'bd': 2, 'bdcolor': color3a},
                        master_kwargs={'font': font2, 'width': window_width, 'text_align': 'center',
                                       'place': {'method': 'pack', 'side': 'bottom', 'fill': 'x', 'expand': False}},
                        animation_kwargs=animation_kwargs,
                    )
                else:
                    buttonframe = tk.Frame(self.checker, bg=mainbg)
                    buttonframe.pack(fill='x')
                    CreateButton(
                        self.checker, 'Запустить в любом случае', quit,
                        default_kwargs={'bg': color3, 'fg': fg, 'r': 8, 'bd': 2, 'bdr': 10, 'bdcolor': color3a},
                        target_kwargs={'bg': color3a, 'fg': fg, 'offset': 0, 'bd': 2, 'bdcolor': color3a},
                        master_kwargs={'font': font2, 'width': window_width // 2, 'text_align': 'center',
                                       'place': {'method': 'pack', 'side': 'left', 'fill': 'x', 'expand': False}},
                        animation_kwargs=animation_kwargs,
                    )
                    CreateButton(
                        self.checker, 'Завершить работу программы', stop,
                        default_kwargs={'bg': color2, 'fg': fg, 'r': 8, 'bd': 2, 'bdr': 10, 'bdcolor': color2a},
                        target_kwargs={'bg': color2a, 'fg': fg, 'offset': 0, 'bd': 2, 'bdcolor': color2a},
                        master_kwargs={'font': font2, 'width': window_width // 2, 'text_align': 'center',
                                       'place': {'method': 'pack', 'side': 'right', 'fill': 'x', 'expand': False}},
                        animation_kwargs=animation_kwargs,
                    )

            WindowManager.PlaceWindow(self.checker, master)
            self.checker.update()
            width = self.checker.winfo_width()
            height = self.checker.winfo_height()
            self.checker.minsize(width, height)
            self.checker.attributes('-alpha', 1)
            infocanvas.add_task(function=infocanvas.animate_out, delay=300)
            infocanvas.animate_in()
            self.checker.mainloop()

    def update_colors(self):
        self.Colors = eval(open('Scheduler_Data/data/colors.dat', 'r', encoding='utf-8').read())

    def update_fonts(self, master=None):
        if master is None:
            master = self.root
        self.Fonts = eval(open('Scheduler_Data/data/fonts.dat', 'r', encoding='utf-8').read())
        font_sizes = eval(open('Scheduler_Data/data/fontsize.dat', 'r', encoding='utf-8').read())
        for i, j in self.Fonts.items():
            size = font_sizes[i]
            parts = j.split('+')
            parts_length = len(parts)
            family = parts[0] if parts_length >= 1 else 'Arial'
            weight = parts[1] if parts_length >= 2 else 'normal'
            slant = parts[2] if parts_length >= 3 else 'roman'
            underline = eval(parts[3]) if parts_length >= 4 else 0
            overstrike = eval(parts[4]) if parts_length >= 5 else 0
            self.Fonts[i] = tk.font.Font(master, family=family, size=size, weight=weight, slant=slant,
                                         underline=underline, overstrike=overstrike)
        self.SCHEDULE_FONT = tk.font.Font(font=self.Fonts['big_title'])
        self.ELLIPSIS_MEASURE = self.SCHEDULE_FONT.measure('...')
        self.SCHEDULE_FONT_LINESPACE = self.SCHEDULE_FONT.metrics('linespace')
        self.SCHEDULE_FONT_LINESPACE_HALF = self.SCHEDULE_FONT_LINESPACE / 2 + 2

    def update_style(self):
        if hasattr(self, 'customStyle'):
            return
        self.customStyle = ttk.Style()
        self.Styles = []
        for i in glob('Scheduler_Data/Themes/*.txt'):
            style_name = os.path.basename(i).split('.')[0]
            shutil.copy(i, 'Scheduler_Data/data/colors.dat')
            self.update_colors()
            self.customStyle.theme_create(style_name, parent='clam',
                                          settings=eval(open('Scheduler_Data/data/tkinterstyle.dat',
                                                             'r', encoding='utf-8').read()))
            self.Styles.append(style_name)

    def update_animation(self, animation):
        match animation[0]:
            case 'Rotate':
                exec(open('Scheduler_Data/Animations/scripts/Rotate.dat', 'r', encoding='utf-8').read(), globals())
                self.RunAnimation = lambda master, filename='Scheduler_Data/images/loading.png', bg=self.Colors['extra'], pady=0: LoadingAnimation(master=master,
                                                                                             filename=filename, bg=bg,
                                                                                             pady=pady)
            case 'Progressbar':
                exec(open('Scheduler_Data/Animations/scripts/Progressbar.dat', 'r', encoding='utf-8').read(), globals())
                self.RunAnimation = lambda master, bg=self.Colors['extra'], interval=10, maximum=None, length=None, padx=15, pady=10: LoadingAnimation(master=master, bg=bg, interval=interval,
                                                                              maximum=maximum, length=length, padx=padx,
                                                                              pady=pady)
            case 'Handle':
                exec(open('Scheduler_Data/Animations/scripts/Handle.dat', 'r', encoding='utf-8').read(), globals())
                self.RunAnimation = lambda master, filename=f'Scheduler_Data/Animations/presets/{animation[1]}.txt', bg=self.Colors['extra'], pady=0: LoadingAnimation(master=master,
                                                                                             filename=filename, bg=bg,
                                                                                             pady=pady)
            case 'GIFPlayer':
                exec(open('Scheduler_Data/Animations/scripts/GIFPlayer.dat', 'r', encoding='utf-8').read(), globals())
                self.RunAnimation = lambda master, filename=f'Scheduler_Data/Animations/GIFs/{animation[1]}.gif', bg=self.Colors['extra'], delay=30, pady=0: LoadingAnimation(master=master,
                                                                                                       filename=filename,
                                                                                                       bg=bg,
                                                                                                       delay=delay,
                                                                                                       pady=pady)
            case _:
                raise ValueError('An error occurred while trying to process user data')

    def get_time_now(self, init=False, resync=False):
        if init and hasattr(self, 'now'):
            return self.now + datetime.timedelta(**self.offset)

        if self.USE_TIME_SERVER:
            if not (init or resync) and time.time() - self.last_sync_time < self.TIME_SYNC_INTERVAL:
                self.now += datetime.timedelta(seconds=1)
                return self.now
            self.last_sync_time = time.time()
            try:
                localtime = time.localtime(self.TIME_CLIENT.request(self.Scheduler_data['time_server']).tx_time)
                self.now = datetime.datetime(year=localtime.tm_year, month=localtime.tm_mon, day=localtime.tm_mday,
                                             hour=localtime.tm_hour, minute=localtime.tm_min, second=localtime.tm_sec)
                self.now += datetime.timedelta(**self.offset)
                return self.now
            except (NTPException, gaierror):
                self.USE_TIME_SERVER = False
                self.Scheduler_data['use_time_server'] = False
                open('Scheduler_Data/data/Scheduler_data.dat', 'w', encoding='utf-8').write(str(self.Scheduler_data))
                window = self.initialize if hasattr(self, 'initialize') else self.root
                showinfo('Ошибка сервера',
                         'Произошла ошибка при попытке подключения к серверу.\n\n'
                         'Будет использоваться локальное время вашего устройства.',
                         window, fg=self.Colors['title1'], bg=self.Colors['main'],
                         animation_kwargs=self.Values['animation_kwargs'])
        self.now = datetime.datetime.now() + datetime.timedelta(**self.offset)
        return self.now

    def set_in_sleep(self, event):
        self.IN_SLEEP[0] = 'Out' in str(event)
        if self.IN_SLEEP[0]:
            self.root.title(f'[Спящий режим] Scheduler - Расписание - {self.Scheduler_data["current_schedule"]}')
        else:
            self.root.title(f'Scheduler - Расписание - {self.Scheduler_data["current_schedule"]}')
            if self.IN_SLEEP[1]:
                self.check_time(resync=True)
                self.IN_SLEEP[1] = False
        return self.IN_SLEEP

    def get_schedule(self):
        try:
            self.schedule = eval(
                open('Scheduler_Data/Schedules/{schedule}.txt'.format(schedule=self.Scheduler_data['current_schedule']),
                     'r',
                     encoding='utf-8').read())
            return self.schedule, False
        except FileNotFoundError:
            files = glob('Scheduler_Data/Schedules/*.txt')
            if files:
                old_schedule = self.Scheduler_data['current_schedule']
                self.Scheduler_data['current_schedule'] = files[0].replace('Scheduler_Data/Schedules/',
                                                                           '').removesuffix('.txt')
                open('Scheduler_Data/data/Scheduler_data.dat', 'w', encoding='utf-8').write(str(self.Scheduler_data))
                self.schedule = eval(
                    open('Scheduler_Data/Schedules/{schedule}.txt'.format(
                        schedule=self.Scheduler_data['current_schedule']), 'r',
                         encoding='utf-8').read())
                showinfo('Внимание',
                         'Указанное расписание \'{old_schedule}\' не найдено, поэтому\n'
                         'будет использоваться другое: \'{new_schedule}\''.format(
                             old_schedule=old_schedule, new_schedule=self.Scheduler_data['current_schedule']),
                         master=self.initialize,
                         fg=self.Colors['title1'], bg=self.Colors['main'],
                         animation_kwargs=self.Values['animation_kwargs'])
                return self.Scheduler_data['current_schedule'], False
            else:
                if askyesno('Ошибка',
                            'Отсутствуют какие-либо расписания.\n'
                            'Открыть меню для создания нового расписания?',
                            master=self.initialize,
                            yes_text='Создать расписание', no_text='Завершить работу',
                            font=self.Fonts['smaller_title'], fg=self.Colors['title1'], bg=self.Colors['main'],
                            cancel_deiconify=False, animation_kwargs=self.Values['animation_kwargs']):
                    return self.create_schedule()
                else:
                    sys.exit()

    def create_schedule_item(self, frame, canvas, info, width=None):
        lesson_number = self.Colors['lesson_number_fg']
        lesson_frame_color1 = self.Colors['lesson_frame1']
        lesson_frame_color2 = self.Colors['lesson_frame2']
        lesson_active_border = self.Colors['lesson_active_border']
        lesson_active_fill = self.Colors['lesson_active_fill']
        title2 = self.Colors['title2']
        title3 = self.Colors['title3']

        i = frame.i
        nl = frame.nl

        lesson = frame.lesson
        if self.SCHEDULE_FONT.measure(lesson) > self.lessonframewidth - 70:
            new_lesson = lesson
            while True:
                new_lesson = new_lesson[:-1]
                if self.SCHEDULE_FONT.measure(new_lesson) <= self.lessonframewidth - 70 - self.ELLIPSIS_MEASURE:
                    break
            lesson = new_lesson + '...'

        frameheight = self.lessonframeheight + nl * 2
        canvas.delete('all')
        create_rounded_rectangle(canvas, 0, 0, self.lessonframewidth, frameheight, (20, 20, 20, 20),
                                 fill=(lesson_frame_color1, lesson_active_border)[width is not None])
        create_rounded_rectangle(canvas, 45, 3, self.lessonframewidth - 3, frameheight - 3,
                                 (16, 16, 16, 16), fill=lesson_frame_color2)
        if width is not None:
            create_rounded_rectangle(canvas, 45, 3, 55, frameheight - 3, (16, 16, 16, 16),
                                     fill=lesson_active_fill)
            progress_width = (self.lessonframewidth - 58) * width + 55
            create_rounded_rectangle(canvas, 50, 3, progress_width, frameheight - 3, (0, 16, 16, 0),
                                     fill=lesson_active_fill)
        canvas.create_text(10, frameheight // 2 - 2, text=str(i + self.startfrom) + self.mark[i],
                           font=self.Fonts['big_title'], fill=(lesson_number, lesson_frame_color2)[width is not None],
                           anchor='w', justify='left')
        canvas.create_text(55, self.SCHEDULE_FONT_LINESPACE_HALF + nl, text=lesson, font=self.Fonts['big_title'],
                           fill=title2, anchor='w',
                           justify='left')
        canvas.create_text(55, frameheight - 20, text=self.duration[i], font=self.Fonts['smaller_title'],
                           fill=title3, anchor='w', justify='left')
        canvas.create_text(self.lessonframewidth - 14, frameheight - 20, text=info,
                           font=self.Fonts['smaller_title'], fill=title3, anchor='e', justify='right')

    def load_schedule(self, ShowLoadingAnimation=True, init=False, root=None):
        if root is None:
            root = self.root
            FULLLOAD = True
        else:
            FULLLOAD = False

        if FULLLOAD:
            self.root.bind('<MouseWheel>', lambda event: None)
            self.root.bind('<Up>', lambda event: None)
            self.root.bind('<Down>', lambda event: None)

        self.all_subjects_length = len(self.schedule['subjects'])
        self.get_time(init=init)

        if hasattr(self, 'scheduleframe'):
            self.scheduleframe.destroy()
            del self.scheduleframe
        if hasattr(self, 'container'):
            self.container.destroy()
            del self.container

        if FULLLOAD:
            def _changeView(event):
                if not self.CHANGEVIEW:
                    return
                self.CHANGEVIEW = False
                self.set_view(self.view + (1, -1)[event == 'back'])
                root.after(0, self.load_schedule)

            def _set_after_change_view():
                def setChangeView():
                    self.CHANGEVIEW = True

                self.root.after(100, setChangeView)

            if hasattr(self, 'mainframe'):
                self.dateframe.destroy()
            else:
                self.mainframe = tk.Frame(self.root, bg=self.Colors['main'])
                self.mainframe.pack(fill='both')

                CreateButton(
                    self.mainframe, None, self.Menu,
                    default_kwargs={'bg': self.Colors['main']},
                    target_kwargs={'bg': self.Colors['shade2'], 'offset': 0},
                    master_kwargs={'image': self.images['menu'],
                                   'place': {'method': 'pack', 'side': 'top', 'fill': 'none', 'expand': False}},
                    animation_kwargs=self.Values['animation_kwargs'],
                )

                tk.Frame(self.mainframe, highlightbackground=self.Colors['separator_color'],
                         highlightthickness=1, height=2).pack(fill='x')

                temp_linespace1 = tk.font.Font(font=self.Fonts['larger_title']).metrics('linespace')
                temp_linespace2 = tk.font.Font(font=self.Fonts['small_title']).metrics('linespace')
                btn_height = temp_linespace1 + temp_linespace2 + 48

                CreateButton(
                    self.mainframe, None, lambda: _changeView('back'),
                    default_kwargs={'bg': self.Colors['main']},
                    target_kwargs={'bg': self.Colors['shade2'], 'offset': 0},
                    master_kwargs={'image': self.images['back'], 'height': btn_height, 'ipadx': 0,
                                   'place': {'method': 'pack', 'side': 'left', 'fill': 'both', 'expand': False}},
                    animation_kwargs=self.Values['animation_kwargs'],
                )
                CreateButton(
                    self.mainframe, None, lambda: _changeView('next'),
                    default_kwargs={'bg': self.Colors['main']},
                    target_kwargs={'bg': self.Colors['shade2'], 'offset': 0},
                    master_kwargs={'image': self.images['next'], 'height': btn_height, 'ipadx': 0,
                                   'place': {'method': 'pack', 'side': 'right', 'fill': 'both', 'expand': False}},
                    animation_kwargs=self.Values['animation_kwargs'],
                )
                self.root.bind('<Left>', lambda event: _changeView('back'))
                self.root.bind('<Right>', lambda event: _changeView('next'))

            title1, title2 = self.get_titles()

            def set_view(event=None):
                self.set_view(self.ChooseDate())
                self.load_schedule(ShowLoadingAnimation=False)

            def _reset_view(event):
                if self.view == 0:
                    return
                self.set_view(0)
                self.load_schedule()

            self.dateframe = tk.Frame(self.mainframe, bg=self.Colors['main'])
            self.dateframe.pack(fill='both', pady=5)

            label1 = tk.Label(self.dateframe, text=title1, font=self.Fonts['larger_title'], bg=self.Colors['main'],
                              fg=self.Colors['title1'])
            label1.pack(padx=5, pady=5)

            label2 = tk.Label(self.dateframe, text=title2, font=self.Fonts['normal_title'], bg=self.Colors['main'],
                              fg=self.Colors['root_label'])
            label2.pack(padx=5, pady=5)

            self.dateframe.bind('<Button-1>', set_view)
            self.dateframe.bind('<Button-2>', _reset_view)
            label1.bind('<Button-1>', set_view)
            label1.bind('<Button-2>', _reset_view)
            label2.bind('<Button-1>', set_view)
            label2.bind('<Button-2>', _reset_view)

            FadeEffect(self.dateframe, self.Colors['shade2'], child=(label1, label2), **self.Values['animation_kwargs'])

        self.widgets = []

        if self.subjects_length == 0:
            self.scheduleframe = tk.Frame(root, bg=self.Colors['lessons_frame_bg'])
            self.scheduleframe.pack(fill='both', expand=True)
            tk.Label(self.scheduleframe, text='Нет уроков', font=self.Fonts['large_title'],
                     bg=self.Colors['lessons_frame_bg'], fg=self.Colors['title2']).pack(pady=10, anchor='center',
                                                                                        fill='both', expand=True)
        else:
            self.container = tk.Frame(root, bg=self.Colors['lessons_frame_bg'])
            self.canvas = tk.Canvas(self.container, width=self.width, height=self.height, highlightthickness=0,
                                    bg=self.Colors['lessons_frame_bg'])
            self.scrollbar = ttk.Scrollbar(self.container, orient='vertical')
            self.scheduleframe = tk.Frame(self.canvas, bg=self.Colors['lessons_frame_bg'])

            self.scheduleframe.bind(
                '<Configure>',
                lambda e: self.canvas.configure(
                    scrollregion=self.canvas.bbox('all')
                )
            )

            self.canvas.create_window((0, 0), window=self.scheduleframe, anchor='nw')
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
            self.canvas.yview_moveto(0)

            self.container.pack(fill='both', expand=True)
            self.canvas.pack(side='left', fill='both', expand=True)
            self.scrollbar.pack(side='right', fill='y')

        self.lessonslist = {}
        for i, j in enumerate(self.subjects):
            if i >= 9:
                break
            lesson = j
            nl = self.SCHEDULE_FONT_LINESPACE * lesson.count('\n')
            lessonframe = tk.Frame(self.scheduleframe, bg=self.Colors['lessons_frame_bg'], width=self.lessonframewidth,
                                   height=self.lessonframeheight + nl * 2)
            lessonframe.i = i
            lessonframe.lesson = lesson
            lessonframe.nl = nl
            lessonframe.pack(padx=10, pady=5, fill='both', expand=True)
            number = i + self.startfrom
            self.lessonslist[number] = lessonframe
            canvas = tk.Canvas(lessonframe, bg=self.Colors['lessons_frame_bg'], width=self.lessonframewidth,
                               height=self.lessonframeheight + nl * 2, highlightthickness=0)
            if FULLLOAD:
                canvas.bind('<Button-1>', lambda event, num=number: self.view_lesson_info(event, root, num))
            canvas.pack(fill='both', expand=True)
            self.create_schedule_item(lessonframe, canvas, '')
            self.widgets.append((lessonframe, canvas))
        self.widgets_length = len(self.widgets)

        if FULLLOAD:
            self.check_time(loop=False, init=init)
            _set_after_change_view()


    def view_lesson_info(self, event, root, number):
        if number not in self.lessonslist:
            return
        frame = self.lessonslist[number]
        viewer = WindowManager.CreateWindow(root, f'Sheduler - Информация о занятии - {frame.lesson}',
                                            bg=self.Colors['main'])
        viewer.protocol('WM_DELETE_WINDOW', viewer.quit)
        viewer.bind('<space>', lambda event: viewer.quit())
        viewer.bind('<Return>', lambda event: viewer.quit())
        viewer.bind('<Escape>', lambda event: viewer.quit())

        tk.Label(viewer, text='Информация о занятии', font=self.Fonts['larger_title'],
                 bg=self.Colors['main'], fg=self.Colors['title1']).pack(padx=5)

        amount_in_week = 0
        current_position_in_week = None
        where_in_week_i = []
        where_in_week = []
        num_counters = []
        maxnum_counter = 0
        most_in_day_counters = {i: 0 for i in range(9)}

        marking = []
        mark_amount_in_week = 0
        mark_where_in_week_i = []
        mark_where_in_week = []
        mark_num_counters = []
        mark_maxnum_counter = 0
        mark_most_in_day_counters = {i: 0 for i in range(9)}
        for i in range(7):
            num_counter = 0
            mark_counter = 0
            sub = self.schedule['subjects'][i]
            stfr = self.schedule['startfrom'][i]
            mark = self.schedule['mark'][i]

            m = []
            for j in range(len(sub)):
                if sub[j] != frame.lesson:
                    m.append(None)
                    continue
                num_counter += 1
                most_in_day_counters[j + stfr] += 1
                ismarked = mark[j] != ''
                m.append(ismarked)
                if i not in where_in_week_i:
                    where_in_week_i.append(i)
                    where_in_week.append(self.WEEKNAMES3[i])
                amount_in_week += 1
                if i == self.weekday and j == frame.i:
                    current_position_in_week = amount_in_week
                if ismarked:
                    mark_counter += 1
                    mark_most_in_day_counters[j + stfr] += 1
                    mark_amount_in_week += 1
                    if i not in mark_where_in_week_i:
                        mark_where_in_week_i.append(i)
                        mark_where_in_week.append(self.WEEKNAMES3[i])
            num_counters.append(num_counter)
            if num_counter > maxnum_counter:
                maxnum_counter = num_counter
            mark_num_counters.append(mark_counter)
            if mark_counter > mark_maxnum_counter:
                mark_maxnum_counter = mark_counter
            marking.append(m)

        most_in_week = []
        mark_most_in_week = []
        for i in range(7):
            if num_counters[i] == maxnum_counter:
                most_in_week.append(self.WEEKNAMES3[i])
            if mark_num_counters[i] == mark_maxnum_counter:
                mark_most_in_week.append(self.WEEKNAMES3[i])

        where_in_day = []
        mark_where_in_day = []
        most_in_day_max = 0
        mark_most_in_day_max = 0
        most_in_day = []
        mark_most_in_day = []
        for j in range(9):
            if most_in_day_counters[j] > 0:
                where_in_day.append(str(j))
            if most_in_day_counters[j] > most_in_day_max:
                most_in_day_max = most_in_day_counters[j]
            if mark_most_in_day_counters[j] > 0:
                mark_where_in_day.append(str(j))
            if mark_most_in_day_counters[j] > mark_most_in_day_max:
                mark_most_in_day_max = mark_most_in_day_counters[j]
        for j in range(9):
            if most_in_day_counters[j] == most_in_day_max:
                most_in_day.append(str(j))
            if mark_most_in_day_counters[j] == mark_most_in_day_max:
                mark_most_in_day.append(str(j))

        infoframe = tk.Frame(viewer, bg=self.Colors['main'])
        infoframe.pack(padx=10, pady=10, anchor='nw')
        tk.Label(infoframe,
                 text=f'Название: {frame.lesson}', font=self.Fonts['big_title'],
                 bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')
        tk.Label(infoframe,
                 text=f'Количество уроков в неделе: {amount_in_week}', font=self.Fonts['big_title'],
                 bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')
        tk.Label(infoframe,
                 text=f'Текущее положение в неделе: {current_position_in_week} / {amount_in_week}',
                 font=self.Fonts['big_title'],
                 bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')
        tk.Label(infoframe, bg=self.Colors['main']).pack(anchor='nw')
        tk.Label(infoframe,
                 text=f'Урок встречается в: {', '.join(where_in_week)}', font=self.Fonts['big_title'],
                 bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')
        tk.Label(infoframe,
                 text=f'Наиболее часто урок встречается в: {', '.join(most_in_week)} (по {maxnum_counter} {declination(maxnum_counter, ('разу', 'раза', 'раз'))})',
                 font=self.Fonts['big_title'],
                 bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')
        tk.Label(infoframe,
                 text=f'Урок встречается {', '.join(where_in_day)} {'уроком' if len(where_in_day) == 1 else 'уроками'}',
                 font=self.Fonts['big_title'],
                 bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')
        tk.Label(infoframe,
                 text=f'Наиболее часто урок встречается {', '.join(most_in_day)} {'уроком' if len(most_in_day) == 1 else 'уроками'} (по {most_in_day_max} {declination(most_in_day_max, ('разу', 'раза', 'раз'))})',
                 font=self.Fonts['big_title'],
                 bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')

        tk.Label(infoframe, bg=self.Colors['main']).pack(anchor='nw')
        if mark_amount_in_week == 0:
            tk.Label(infoframe,
                     text=f'Уроков с отметкой нет', font=self.Fonts['big_title'],
                     bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')
        else:
            tk.Label(infoframe,
                     text=f'Количество уроков с отметкой: {mark_amount_in_week}',
                     font=self.Fonts['big_title'],
                     bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')
            tk.Label(infoframe,
                     text=f'Отметки встречается в: {', '.join(mark_where_in_week)}',
                     font=self.Fonts['big_title'],
                     bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')
            tk.Label(infoframe,
                     text=f'Наиболее часто отметки встречается в: {', '.join(mark_most_in_week)} (по {mark_maxnum_counter} {declination(mark_maxnum_counter, ('разу', 'раза', 'раз'))})',
                     font=self.Fonts['big_title'],
                     bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')
            tk.Label(infoframe,
                     text=f'Отметки встречаются {', '.join(mark_where_in_day)} {'уроком' if len(mark_where_in_day) == 1 else 'уроками'}',
                     font=self.Fonts['big_title'],
                     bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')
            tk.Label(infoframe,
                     text=f'Наиболее часто отметки встречаются {', '.join(mark_most_in_day)} {'уроком' if len(mark_most_in_day) == 1 else 'уроками'} (по {mark_most_in_day_max} {declination(mark_most_in_day_max, ('разу', 'раза', 'раз'))})',
                     font=self.Fonts['big_title'],
                     bg=self.Colors['main'], fg=self.Colors['title2']).pack(anchor='nw')

        viewer.update_idletasks()
        CreateButton(
            viewer, 'Понятно!', viewer.quit,
            default_kwargs={'bg': self.Colors['color1'], 'fg': self.Colors['title1'],
                            'r': 8, 'bd': 2, 'bdr': 10, 'bdcolor': self.Colors['color1a']},
            target_kwargs={'bg': self.Colors['color1a'], 'offset': 0,
                           'bd': 2, 'bdcolor': self.Colors['color1a']},
            master_kwargs={'font': self.Fonts['bigger_title'], 'width': viewer.winfo_width(),
                           'text_align': 'center',
                           'place': {'method': 'pack', 'side': 'bottom', 'fill': 'x', 'expand': False}},
            animation_kwargs=self.Values['animation_kwargs']
        )

        master_state = root.state()
        WindowManager.PlaceWindow(viewer, root)
        viewer.mainloop()

        viewer.destroy()
        if master_state == 'zoomed':
            root.state('zoomed')
        root.deiconify()

    def get_titles(self, now=None, view=None):
        if now is None:
            now = self.now
        if view is None:
            view = self.view

        date = now + datetime.timedelta(days=view)
        if -1 <= view <= 1:
            title1 = ('Вчера', 'Сегодня', 'Завтра')[view + 1]
            title2 = f'{self.WEEKNAMES[date.weekday()]}, {date.day} {self.MONTHNAMES2[date.month - 1]}'
        else:
            title1 = self.WEEKNAMES[date.weekday()]
            title2 = f'{date.day} {self.MONTHNAMES2[date.month - 1]}'
        return title1, title2

    def get_time(self, init=False, resync=False):
        last_date = self.now.date()
        self.get_time_now(init=init, resync=resync)
        self.new_date = last_date != self.now.date() or self.new_view
        self.new_view = False
        if self.new_date or init or resync:
            self.weekday = self.now.weekday() + self.view
            if 0 > self.weekday or self.weekday >= self.all_subjects_length:
                self.weekday %= 7
            self.subjects = self.schedule['subjects'][self.weekday]
            self.subjects_length = len(self.subjects)
            self.duration = tuple(
                i.replace(' ', '').replace('-', ' - ') for i in self.schedule['duration'][self.weekday])
            self.startfrom = self.schedule['startfrom'][self.weekday]
            self.mark = self.schedule['mark'][self.weekday]
        return self.now

    def check_time(self, loop=True, init=False, resync=False):
        if self.IN_SLEEP[0]:
            self.IN_SLEEP[1] = True
            return
        self.get_time(init=init, resync=resync)

        if self.view == 0 and self.new_date:
            self.load_schedule()
            return

        if self.view == 0:
            checked = False
            for i, j in enumerate(self.duration):
                if i >= self.widgets_length:
                    break

                interval = j.split(' - ')
                delta = self.getdatetime(interval[self.now > self.getdatetime(interval[0])]) - self.now
                deltasec = self.ROUND_TIME_FUNCTION(delta.total_seconds())
                deltamin = self.ROUND_TIME_FUNCTION(deltasec / 60)
                deltahour = int(deltamin / 60)
                duration = (self.getdatetime(interval[1]) - self.getdatetime(interval[0])).total_seconds()

                if self.getdatetime(interval[0]) <= self.now < self.getdatetime(interval[1]):
                    checked = True
                    if deltahour > 0:
                        if deltamin > 0:
                            text = 'Закончится через {deltahour} {hours} {deltamin} {minutes}'.format(
                                deltahour=deltahour, hours=declination(deltahour, ('час', 'часа', 'часов')),
                                deltamin=deltamin % 60,
                                minutes=declination(deltamin % 60, ('минуту', 'минуты', 'минут')))
                        else:
                            text = 'Закончится через {deltahour} {hours}'.format(deltahour=deltahour,
                                                                                 hours=declination(deltahour,
                                                                                                   ('час', 'часа',
                                                                                                    'часов')))
                    elif deltamin > 0:
                        text = 'Закончится через {delta} {minutes}'.format(delta=deltamin, minutes=declination(deltamin,
                                                                                                               ('минуту',
                                                                                                                'минуты',
                                                                                                                'минут')))
                    elif deltasec > 0:
                        text = 'Закончится через {delta} {seconds}'.format(delta=deltasec, seconds=declination(deltasec,
                                                                                                               ('секунду',
                                                                                                                'секунды',
                                                                                                                'секунд')))
                    else:
                        text = 'Закончится сейчас'
                    try:
                        self.create_schedule_item(self.widgets[i][0], self.widgets[i][1], text,
                                                  (duration - deltasec) / duration)
                    except IndexError:
                        pass
                    continue
                if delta >= datetime.timedelta(hours=1):
                    try:
                        self.create_schedule_item(self.widgets[i][0], self.widgets[i][1], '')
                    except IndexError:
                        pass
                    continue
                if (i == 0 and self.now < self.getdatetime(interval[0])) or (
                        i <= self.subjects_length and self.now < self.getdatetime(self.duration[i].split(' - ')[0])):
                    if checked:
                        text = ''
                    else:
                        checked = True
                        if deltamin > 0:
                            text = 'Начнётся через {delta} {minutes}'.format(delta=deltamin,
                                                                             minutes=declination(deltamin,
                                                                                                 ('минуту', 'минуты',
                                                                                                  'минут')))
                        elif deltasec > 0:
                            text = 'Начнётся через {delta} {seconds}'.format(delta=deltasec,
                                                                             seconds=declination(deltasec,
                                                                                                 ('секунду', 'секунды',
                                                                                                  'секунд')))
                        else:
                            text = 'Начнётся сейчас'
                    try:
                        self.create_schedule_item(self.widgets[i][0], self.widgets[i][1], text)
                    except IndexError:
                        pass
                    continue
                if self.getdatetime(interval[1]) < self.now:
                    if checked:
                        text = ''
                    else:
                        text = f'{" " * 31}Урок окончен'
                    try:
                        self.create_schedule_item(self.widgets[i][0], self.widgets[i][1], text)
                    except IndexError:
                        pass
        elif self.view < 0:
            for i in range(self.widgets_length):
                try:
                    self.create_schedule_item(self.widgets[i][0], self.widgets[i][1], f'{" " * 31}Урок окончен')
                except IndexError:
                    pass
        else:
            for i in range(self.widgets_length):
                try:
                    self.create_schedule_item(self.widgets[i][0], self.widgets[i][1], '')
                except IndexError:
                    pass

        try:
            self.root.update_idletasks()
            self.width, self.height = self.scheduleframe.winfo_width(), self.scheduleframe.winfo_height()
            self.canvas.configure(width=self.width, height=self.height)
        except (tk.TclError, AttributeError):
            pass

        if loop:
            self.last_after = self.root.after(1000, self.check_time)

    def getdatetime(self, my_time, format=None):
        if format is None:
            format = '%d.%m.%Y %H:%M'
        my_time = time.strptime(f'{self.now.strftime("%d.%m.%Y")} {my_time}', format)
        my_time = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=calendar.timegm(my_time))
        return my_time

    def ChooseDate(self, master=None, view=None, mindate=None, maxdate=None, today=None, bg=None, fg=None):
        if master is None:
            master = self.root
        if view is None:
            view = self.view
        if today is None:
            today = self.now
        if bg is None:
            bg = self.Colors['main']
        if fg is None:
            fg = self.Colors['title1']

        self.customStyle.theme_use('clam')
        self.view2 = view

        win = WindowManager.CreateWindow(master, 'Scheduler - Выберите дату', bg)
        current = today + datetime.timedelta(days=view)
        cal = Calendar(win, font=self.Fonts['big_title'], selectmode='day', locale='ru_RU',
                       mindate=mindate, maxdate=maxdate, background=bg, foreground=fg,
                       borderwidth=5, showweeknumbers=False, showothermonthdays=False,
                       selectbackground=self.Colors['calendar_select_bg'],
                       selectforeground=self.Colors['calendar_select_fg'],
                       weekendbackground=self.Colors['calendar_weekend_bg'],
                       weekendforeground=self.Colors['calendar_weekend_fg'],
                       normalbackground=self.Colors['calendar_normal_bg'],
                       normalforeground=self.Colors['calendar_normal_fg'],
                       year=current.year, month=current.month, day=current.day)

        cal.calevent_create(current, 'Текущий выбор', 'current')
        cal.tag_config('current', background=self.Colors['calendar_current_bg'],
                       foreground=self.Colors['calendar_current_fg'])
        cal.calevent_create(today, 'Сегодня', 'today')
        cal.tag_config('today', background=self.Colors['calendar_today_bg'],
                       foreground=self.Colors['calendar_today_fg'])
        cal.selection_set(current)

        def _getdate(event=None):
            self.view2 = (cal.selection_get() - self.now.date()).days
            win.quit()

        def _select_and_getdate(lbl):
            day = lbl['text']
            if not day:
                return
            month, year = cal.get_displayed_month()
            date = datetime.date(year, month, int(day))
            if mindate is not None and date < mindate.date() or maxdate is not None and date > maxdate.date():
                return
            cal.selection_set(date)
            win.update()
            _getdate()

        def _reset_date(event):
            cal.selection_set(today)
            win.update()
            _getdate()

        for row in cal._calendar:
            for lbl in row:
                lbl.bind('<Double-1>', _getdate)
                lbl.bind('<Button-2>', _reset_date)
                lbl.bind('<Button-3>', lambda event, lbl=lbl: _select_and_getdate(lbl))
        cal.pack(fill='both', expand=True)
        win.protocol('WM_DELETE_WINDOW', win.quit)
        win.bind('<Escape>', lambda event: win.quit())
        master_state = self.root.state()
        WindowManager.PlaceWindow(win, master)
        win.focus_force()
        win.mainloop()

        if master == self.root and master_state == 'zoomed':
            self.root.state('zoomed')

        win.destroy()
        self.customStyle.theme_use(self.CURRENT_THEME)
        master.deiconify()
        master.focus_force()
        return self.view2

    def PackBackpack(self, master=None, bg=None):
        if master is None:
            master = self.root
        if bg is None:
            bg = self.Colors['main']

        win = WindowManager.CreateWindow(master, 'Scheduler - Сборка рюкзака', bg, switch_fullscreen=False)

        for i in range(self.now.weekday(), self.now.weekday() - 7, -1):
            if self.schedule['subjects'][i]:
                break
        self.viewfrom = self.now.date() - datetime.timedelta(days=self.now.weekday() - i)
        for i in range(self.now.weekday() + 1, self.now.weekday() + 7):
            if self.schedule['subjects'][i % 7]:
                break
        self.viewto = self.now.date() + datetime.timedelta(days=i - self.now.weekday())

        def _getpackfromdate(event=None):
            if event:
                self.view2 = self.ChooseDate(win, view=self.viewfromday, today=self.now)
            else:
                self.view2 = (self.viewfrom - self.now.date()).days

            self.viewfromday = self.view2
            self.viewfrom = self.now + datetime.timedelta(days=self.view2)

            if type(self.viewfrom) is not datetime.date:
                self.viewfrom = self.viewfrom.date()
            if type(self.viewto) is not datetime.date:
                self.viewto = self.viewto.date()
            if self.viewfrom >= self.viewto:
                self.viewto = self.viewfrom + datetime.timedelta(days=1)
                _getpacktodate()

            title1, title2 = self.get_titles(self.now, self.viewfromday)
            packfrom.configure('out', text=f'{title1}, {title2}')
            _getpackinginstruction()

        def _getpacktodate(event=None):
            if event:
                self.view2 = self.ChooseDate(win, view=self.viewtoday, today=self.now)
            else:
                self.view2 = (self.viewto - self.now.date()).days

            self.viewtoday = self.view2
            self.viewto = self.now + datetime.timedelta(days=self.view2)

            if type(self.viewfrom) is not datetime.date:
                self.viewfrom = self.viewfrom.date()
            if type(self.viewto) is not datetime.date:
                self.viewto = self.viewto.date()
            if self.viewto <= self.viewfrom:
                self.viewfrom = self.viewto - datetime.timedelta(days=1)
                _getpackfromdate()

            title1, title2 = self.get_titles(self.now, self.viewtoday)
            packto.configure('out', text=f'{title1}, {title2}')
            _getpackinginstruction()

        def _getpackinginstruction():
            if hasattr(self, 'tip'):
                self.tip.destroy()
            if hasattr(self, 'finish'):
                self.finish.canvas.destroy()

            subjects = self.schedule['subjects']
            packingfrom = subjects[self.viewfrom.weekday()]
            packingto = subjects[self.viewto.weekday()]
            packingfromset = set(packingfrom)
            packingtoset = set(packingto)
            toremoveset = packingfromset - packingtoset
            toaddset = packingtoset - packingfromset

            toremove = []
            toadd = []
            tocheck = []

            for i in packingfrom:
                if i in toremoveset and i not in toremove:
                    toremove.append(i)

            for i in packingto:
                if i in toaddset and i not in toadd:
                    toadd.append(i)
                if i not in tocheck:
                    tocheck.append(i)

            win.bind('<MouseWheel>', lambda event: None)
            win.bind('<Up>', lambda event: None)
            win.bind('<Down>', lambda event: None)

            if hasattr(self, 'scrollbar2'):
                try:
                    self.scrollbar2.configure(command=lambda *args: None)
                except tk.TclError:
                    pass
            if hasattr(self, 'scrolltainer'):
                self.scrolltainer.destroy()
                del self.scrolltainer
            if hasattr(self, 'instruction'):
                self.instruction.destroy()
                del self.instruction

            fonttitle = self.Fonts['bigger_normal_title']
            fontobj = self.Fonts['small_title']
            fgtitle = self.Colors['title2']
            fgobj = self.Colors['title3']
            activefgtitle = self.Colors['active_fg_title']
            activefgobj = self.Colors['active_fg_obj']
            donefgtitle = self.Colors['done_fg_title']
            donefgobj = self.Colors['done_fg_obj']
            underline = 0
            strike = 0
            activeunderline = 1
            activestrike = 0
            doneunderline = 0
            donestrike = 1

            self.toremovedone = True
            self.toadddone = True
            self.tocheckdone = True

            if not toadd:
                win.bind('<MouseWheel>', lambda event: None)
                win.bind('<Up>', lambda event: None)
                win.bind('<Down>', lambda event: None)
                self.instruction = tk.Frame(win, bg=self.Colors['shade1'], bd=0)
                self.instruction.grid(padx=10)
                text = ('Сборка не требуется: уроки идентичны.',
                        'Сборка не требуется: уроков нет.')[bool(toremove)]
                tk.Label(self.instruction, text=text, bg=self.Colors['shade1'], fg=fgtitle,
                         font=self.Fonts['normal_title']).grid(padx=5, pady=5, sticky='w')

            else:
                self.scrolltainer = tk.Frame(win, bd=0)
                container = tk.Frame(self.scrolltainer, bd=0, bg=self.Colors['shade1'])
                self.canvas2 = tk.Canvas(container, highlightthickness=0, width=500, height=500,
                                         bg=self.Colors['shade1'])
                self.scrollbar2 = ttk.Scrollbar(container, orient='vertical')
                self.instruction = tk.Frame(self.canvas2, bg=self.Colors['shade1'], bd=0)

                self.instruction.bind(
                    '<Configure>',
                    lambda e: self.canvas2.configure(
                        scrollregion=self.canvas2.bbox('all')
                    )
                )

                self.canvas2.create_window((0, 0), window=self.instruction, anchor='nw')
                self.canvas2.configure(yscrollcommand=self.scrollbar2.set)
                self.canvas2.yview_moveto(0)

                self.scrolltainer.grid(padx=10)
                container.pack(fill='both', expand=True)
                self.canvas2.pack(side='left', fill='both', expand=True)
                self.scrollbar2.pack(side='right', fill='y')

                def _click_on_object(op, title, widgets, obj=None):
                    is_done = self.__dict__[f'to{op}done']
                    if is_done:
                        if obj is None:
                            title.configure('in', default_kwargs={'fg': fgtitle, 'strike_width': strike},
                                            target_kwargs={'strike_width': activestrike})
                            title.fix_target_decoration()
                            for i in widgets:
                                i.configure('out', default_kwargs={'fg': fgobj, 'strike_width': strike},
                                            target_kwargs={'strike_width': activestrike})
                                i.fix_target_decoration()
                        else:
                            title.configure('out', default_kwargs={'fg': fgtitle, 'strike_width': strike},
                                            target_kwargs={'strike_width': activestrike})
                            title.fix_target_decoration()
                            obj.configure('in',
                                          default_kwargs={'fg': fgobj, 'strike_width': strike},
                                          target_kwargs={'strike_width': activestrike})
                            obj.fix_target_decoration()
                        self.__dict__[f'to{op}done'] = False
                    else:
                        if obj is None:
                            title.configure('in', default_kwargs={'fg': donefgtitle, 'strike_width': donestrike},
                                            target_kwargs={'strike_width': donestrike})
                            title.fix_default_decoration()
                            for i in widgets:
                                i.configure('out', default_kwargs={'fg': donefgobj, 'strike_width': donestrike},
                                            target_kwargs={'strike_width': donestrike})
                                i.fix_default_decoration()
                            self.__dict__[f'to{op}done'] = True
                        else:
                            if obj.target_kwargs['strike_width'] == strike:
                                obj.configure('in', default_kwargs={'fg': donefgobj, 'strike_width': donestrike},
                                              target_kwargs={'strike_width': donestrike})
                                obj.fix_default_decoration()
                            else:
                                obj.configure('in', default_kwargs={'fg': fgobj, 'strike_width': strike},
                                              target_kwargs={'strike_width': activestrike})
                                obj.fix_target_decoration()
                            if not any(i.target_kwargs['strike_width'] == strike for i in widgets):
                                title.configure('out', default_kwargs={'fg': donefgtitle, 'strike_width': donestrike},
                                                target_kwargs={'strike_width': donestrike})
                                title.fix_default_decoration()
                                self.__dict__[f'to{op}done'] = True
                    self.finish.configure('out', master_kwargs={
                        'state': ('disabled', 'normal')[all((self.toadddone, self.toremovedone, self.tocheckdone))]})

                def create_sector(op):
                    self.__dict__[f'to{op}done'] = False
                    text = {'remove': 'Уберите:',
                            'add': 'Подготовьте:',
                            'check': 'Проверьте:'}[op]
                    title = CreateButton(
                        self.instruction, text,
                        default_kwargs={'bg': self.Colors['shade1'], 'fg': fgtitle, 'strike_width': strike},
                        target_kwargs={'bg': self.Colors['shade3'], 'fg': activefgtitle, 'offset': 14,
                                       'strike_width': activestrike},
                        master_kwargs={'font': fonttitle, 'hidden_text': '>', 'width': 500,
                                       'place': {'method': 'grid', 'sticky': 'w'}},
                        animation_kwargs=self.Values['animation_kwargs']
                    )
                    title.fix_target_decoration()

                    widgets = []
                    for i, j in enumerate(variables[f'to{op}']):
                        obj = CreateButton(
                            self.instruction, f'{i + 1}. {j}',
                            default_kwargs={'bg': self.Colors['shade1'], 'fg': fgobj, 'strike_width': strike},
                            target_kwargs={'bg': self.Colors['shade3'], 'fg': activefgobj, 'offset': 14,
                                           'strike_width': activestrike},
                            master_kwargs={'font': fontobj, 'hidden_text': '>', 'width': 500, 'padx': 20, 'pady': 0,
                                           'ipady': 4,
                                           'place': {'method': 'grid', 'sticky': 'w'}},
                            animation_kwargs=self.Values['animation_kwargs']
                        )
                        obj.canvas.bind('<Button-1>',
                                        lambda event, op=op, title=title, obj=obj: _click_on_object(op, title, widgets,
                                                                                                    obj))
                        obj.fix_target_decoration()
                        widgets.append(obj)
                        self.objects.append(obj.canvas)
                        self.obj_params.append((op, title, widgets, obj))
                    title.canvas.bind('<Button-1>',
                                      lambda event, op=op, title=title: _click_on_object(op, title, widgets))
                    self.sectors.append((widgets, title, op))

                variables = locals()
                self.objects = []
                self.obj_params = []
                self.sectors = []

                if toadd:
                    if toremove:
                        create_sector('remove')
                    create_sector('add')
                    create_sector('check')

                    self.tip = tk.Label(win, text='Нажимайте на пункты плана, чтобы пометить\n'
                                                  'их выполненными или вернуть обратно.\n\n'
                                                  'Когда все пункты будут выполнены,\n'
                                                  'кнопка ниже станет активной.', bg=bg,
                                        fg=self.Colors['title1'],
                                        font=self.Fonts['text'])
                    self.tip.grid(padx=5, pady=5)

                    # Переменные для отслеживания перетаскивания
                    self.drag_data = {
                        'active': False,
                        'start_index': None,
                        'start_state': None,
                        'last_index': None,
                        'last_y': None,
                        'direction': None,
                        'return_to_initial_states': False,
                        'initial_states': []  # Будем хранить исходные состояния всех элементов
                    }

                    def on_click(event, index):
                        op, title, widgets, obj = self.obj_params[index]
                        # Запоминаем начальные данные
                        self.drag_data['start_index'] = index
                        self.drag_data['start_state'] = (obj.target_kwargs['strike_width'] == strike)
                        self.drag_data['last_index'] = index
                        self.drag_data['last_y'] = event.y_root
                        self.drag_data['direction'] = None
                        self.drag_data['active'] = True

                        self.drag_data['return_to_initial_states'] = False

                        # Сохраняем исходные состояния всех элементов
                        self.drag_data['initial_states'] = [
                            (obj.target_kwargs['strike_width'] == strike) for obj in [p[3] for p in self.obj_params]
                        ]

                    def on_motion(event):
                        if not self.drag_data['active']:
                            return

                        # Определяем текущий элемент под курсором
                        widget = event.widget.winfo_containing(event.x_root, event.y_root)
                        if widget not in self.objects:
                            return

                        current_index = self.objects.index(widget)
                        current_y = event.y_root

                        # Если это тот же элемент, что и ранее, ничего не делаем
                        if current_index == self.drag_data['last_index']:
                            return

                        # Определяем направление движения по Y-координате
                        current_direction = 'up' if current_y < self.drag_data['last_y'] else 'down'

                        # Если направление еще не определено, устанавливаем его
                        if self.drag_data['direction'] is None:
                            self.drag_data['direction'] = current_direction
                        # Если направление изменилось, восстанавливаем исходные состояния
                        elif current_direction != self.drag_data['direction']:
                            # Обновляем начальную точку и состояние
                            self.drag_data['start_index'] = self.drag_data['last_index']
                            self.drag_data['start_state'] = not self.drag_data['start_state']
                            self.drag_data['direction'] = current_direction

                            self.drag_data['return_to_initial_states'] = not self.drag_data['return_to_initial_states']

                            # Обновляем секции
                            update_sections()
                            return

                        # Применяем изменение состояния к элементам между последним и текущим
                        start_idx = min(self.drag_data['last_index'], current_index)
                        end_idx = max(self.drag_data['last_index'], current_index)

                        # Если возвращаемся к исходным состояниям, применяем их
                        if self.drag_data['return_to_initial_states']:
                            for idx in range(start_idx, end_idx + 1):
                                op, title, widgets, obj = self.obj_params[idx]
                                if self.drag_data['initial_states'][idx]:
                                    obj.configure('out',
                                                  default_kwargs={'fg': fgobj, 'strike_width': strike},
                                                  target_kwargs={'strike_width': activestrike})
                                    obj.fix_target_decoration()
                                else:
                                    obj.configure('out', default_kwargs={'fg': donefgobj, 'strike_width': donestrike},
                                                  target_kwargs={'strike_width': donestrike})
                                    obj.fix_default_decoration()
                        else:
                            for idx in range(start_idx, end_idx + 1):
                                op, title, widgets, obj = self.obj_params[idx]

                                # Применяем начальное состояние ко всем элементам в диапазоне
                                if self.drag_data['start_state']:
                                    obj.configure('out', default_kwargs={'fg': donefgobj, 'strike_width': donestrike},
                                                  target_kwargs={'strike_width': donestrike})
                                    obj.fix_default_decoration()
                                else:
                                    obj.configure('out',
                                                  default_kwargs={'fg': fgobj, 'strike_width': strike},
                                                  target_kwargs={'strike_width': activestrike})
                                    obj.fix_target_decoration()

                        self.drag_data['last_index'] = current_index
                        self.drag_data['last_y'] = current_y

                        # Обновляем состояние секций
                        update_sections()

                    def update_sections():
                        for i in self.sectors:
                            if not any(j.target_kwargs['strike_width'] == strike for j in i[0]):
                                i[1].configure('out', default_kwargs={'fg': donefgtitle, 'strike_width': donestrike},
                                               target_kwargs={'strike_width': donestrike})
                                i[1].fix_default_decoration()
                                self.__dict__[f'to{i[2]}done'] = True
                            else:
                                i[1].configure('out',
                                               default_kwargs={'fg': fgtitle, 'strike_width': strike},
                                               target_kwargs={'strike_width': activestrike})
                                i[1].fix_target_decoration()
                                self.__dict__[f'to{i[2]}done'] = False
                        self.finish.configure('out', master_kwargs={'state': ('disabled', 'normal')[
                            all((self.toadddone, self.toremovedone, self.tocheckdone))]})

                    def on_release(event):
                        if not self.drag_data['active']:
                            return

                        self.drag_data['active'] = False

                        # Если не было движения, это обычный клик - переключаем состояние
                        if self.drag_data['last_index'] == self.drag_data['start_index']:
                            index = self.drag_data['start_index']
                            op, title, widgets, obj = self.obj_params[index]
                            _click_on_object(op, title, widgets, obj)
                        else:
                            # После перетаскивания обновляем секции
                            update_sections()

                    # Модифицируем создание объектов для добавления обработчиков перетаскивания
                    for i, (op, title, widgets, obj) in enumerate(self.obj_params):
                        # Обработчик клика (не перетаскивания)
                        obj.canvas.bind('<ButtonPress-1>',
                                        lambda e, idx=i: on_click(e, idx))
                        obj.canvas.bind('<B1-Motion>', on_motion)
                        obj.canvas.bind('<ButtonRelease-1>', on_release)

                win.update_idletasks()
                if self.instruction.winfo_height() > self.canvas2.winfo_height():
                    self.scrollbar2.configure(command=self.canvas2.yview)
                    win.bind('<MouseWheel>', lambda event: WindowManager.on_mousewheel(event, self.canvas2))
                    win.bind('<Up>', lambda event: self.canvas2.yview_scroll(-2, 'units'))
                    win.bind('<Down>', lambda event: self.canvas2.yview_scroll(2, 'units'))

            self.finish = CreateButton(
                win, 'Рюкзак собран!',
                lambda: _checkpacking() if self.finish.master_kwargs['state'] == 'normal' else None,
                default_kwargs={'bg': self.Colors['extra'], 'fg': self.Colors['title1'], 'disabled_bg': bg,
                                'disabled_fg': self.Colors['shade3'], 'r': 8, 'bd': 2, 'bdr': 10,
                                'bdcolor': self.Colors['shade2'], 'disabled_bdcolor': self.Colors['shade3']},
                target_kwargs={'bg': self.Colors['shade2'], 'fg': self.Colors['title1'], 'disabled_bg': bg,
                               'disabled_fg': self.Colors['shade3'], 'r': 8, 'bd': 2, 'offset': 0,
                               'bdcolor': self.Colors['shade2'], 'disabled_bdr': 10,
                               'disabled_bdcolor': self.Colors['shade2']},
                master_kwargs={'font': self.Fonts['bigger_title'], 'width': 535, 'text_align': 'center',
                               'state': ('disabled', 'normal')[
                                   all((self.toadddone, self.toremovedone, self.tocheckdone))],
                               'place': {'method': 'grid', 'sticky': 'w'}},
                animation_kwargs=self.Values['animation_kwargs'],
            )
            self.finish.animate_out()

        def _checkpacking(event=None, needask=True):
            if all((self.toadddone, self.toremovedone, self.tocheckdone)) or (
                    needask and askyesno('Выход', 'Сборка была не завершена.\nВы уверены, что хотите выйти?',
                                         master=win, font=self.Fonts['smaller_title'], fg=self.Colors['title1'],
                                         bg=self.Colors['main'],
                                         animation_kwargs=self.Values['animation_kwargs'])):
                win.quit()
            else:
                win.focus_force()

        tk.Label(win, text='Провести сборку с', bg=bg, fg=self.Colors['title1'], font=self.Fonts['small_title']).grid(
            padx=5, pady=5, sticky='w')
        packfrom = CreateButton(
            win, '', _getpackfromdate, True,
            default_kwargs={'bg': bg, 'fg': self.Colors['title1']},
            target_kwargs={'bg': self.Colors['shade2'], 'fg': self.Colors['title1'], 'offset': 14},
            master_kwargs={'font': self.Fonts['bigger_normal_title'], 'hidden_text': '>',
                           'place': {'method': 'grid', 'sticky': 'w'}},
            animation_kwargs=self.Values['animation_kwargs']
        )

        tk.Label(win, text='на', bg=bg, fg=self.Colors['title1'], font=self.Fonts['small_title']).grid(padx=5, pady=5,
                                                                                                       sticky='w')
        packto = CreateButton(
            win, '', _getpacktodate, True,
            default_kwargs={'bg': bg, 'fg': self.Colors['title1']},
            target_kwargs={'bg': self.Colors['shade2'], 'fg': self.Colors['title1'], 'offset': 14},
            master_kwargs={'font': self.Fonts['bigger_normal_title'], 'hidden_text': '>',
                           'place': {'method': 'grid', 'sticky': 'w'}},
            animation_kwargs=self.Values['animation_kwargs']
        )

        tk.Frame(win, highlightbackground=self.Colors['separator_color'], highlightthickness=1, height=2).grid(pady=10,
                                                                                                               sticky='nesw')

        _getpackfromdate()
        _getpacktodate()

        win.protocol('WM_DELETE_WINDOW', _checkpacking)
        win.bind('<space>', lambda event: _checkpacking(needask=False))
        win.bind('<Return>', lambda event: _checkpacking(needask=False))
        win.bind('<Escape>', _checkpacking)
        master_state = self.root.state()
        WindowManager.PlaceWindow(win, master)
        win.focus_force()
        win.mainloop()

        if master == self.root and master_state == 'zoomed':
            self.root.state('zoomed')

        win.destroy()
        master.deiconify()
        master.focus_force()

    def Menu(self, master=None, bg=None, fg=None):
        if master is None:
            master = self.root
        if bg is None:
            bg = self.Colors['extra']
        if fg is None:
            fg = self.Colors['title1']
        menu = WindowManager.CreateWindow(master=master, title='Scheduler - Меню', bg=bg, attrs={'-alpha': 0})

        self.Scheduler_data = eval(open('Scheduler_Data/data/Scheduler_data.dat', 'r', encoding='utf-8').read())
        self.NEW_DATA = dict()
        for i, j in self.Scheduler_data.items():
            self.NEW_DATA[i] = j
        self.old_offset = self.offset.copy()
        self.TO_DELETE_SCHEDULES = []

        checkbox_images = (tk.PhotoImage(file='Scheduler_Data/images/checkbox_blank.png'),
                           tk.PhotoImage(file='Scheduler_Data/images/checkbox_fill.png'))

        def choose_data(data_name):
            def select():
                _set_delay()
                self.NEW_DATA[data_name] = self.selection

                match data_name:
                    case 'font':
                        shutil.copy(f'Scheduler_Data/Fonts/{self.selection}/{self.selection}.dat',
                                    f'Scheduler_Data/data/fonts.dat')
                        self.update_fonts()
                    case 'fontsize':
                        shutil.copy(f'Scheduler_Data/FontSizes/{self.selection}.txt',
                                    f'Scheduler_Data/data/fontsize.dat')
                        self.update_fonts()
                    case 'theme':
                        shutil.copy(f'Scheduler_Data/Themes/{self.selection}.txt', f'Scheduler_Data/data/colors.dat')
                        self.update_colors()
                        self.customStyle.theme_use(self.selection)
                    case 'animation':
                        pass
                    case _:
                        raise ValueError(f'Invalid data name \'{data_name}\'')

                load_widgets(reload=True)

            def _set_delay():
                def switch():
                    self.delay = False

                self.delay = True
                selector.after(100, switch)

            def _back(event=None):
                if self.delay:
                    return

                i = options.index(self.selection)
                if i == 0:
                    self.selection = options[-1]
                else:
                    self.selection = options[i - 1]
                select()

            def _next(event=None):
                if self.delay:
                    return

                i = options.index(self.selection)
                if i == len(options) - 1:
                    self.selection = options[0]
                else:
                    self.selection = options[i + 1]
                select()

            def load_widgets(reload=False):
                if reload:
                    self.controlpanel.destroy()
                    self.back_button.canvas.destroy()
                    self.next_button.canvas.destroy()
                    self.select_text.destroy()
                    self.info.destroy()
                    self.save_button.canvas.destroy()

                self.controlpanel = tk.Frame(selector, bg=self.Colors['extra'])
                self.controlpanel.pack(fill='both')

                temp_linespace1 = tk.font.Font(font=self.Fonts['larger_title']).metrics('linespace')
                temp_linespace2 = tk.font.Font(font=self.Fonts['small_title']).metrics('linespace')
                btn_height = temp_linespace1 + temp_linespace2 + 32

                self.back_button = CreateButton(
                    self.controlpanel, None, _back,
                    default_kwargs={'bg': self.Colors['extra']},
                    target_kwargs={'bg': self.Colors['shade2'], 'offset': 0},
                    master_kwargs={'image': self.images['back'], 'height': btn_height, 'ipadx': 0,
                                   'place': {'method': 'pack', 'side': 'left', 'fill': 'both', 'expand': False}},
                    animation_kwargs=self.Values['animation_kwargs'],
                )
                self.next_button = CreateButton(
                    self.controlpanel, None, _next,
                    default_kwargs={'bg': self.Colors['extra']},
                    target_kwargs={'bg': self.Colors['shade2'], 'offset': 0},
                    master_kwargs={'image': self.images['next'], 'height': btn_height, 'ipadx': 0,
                                   'place': {'method': 'pack', 'side': 'right', 'fill': 'both', 'expand': False}},
                    animation_kwargs=self.Values['animation_kwargs'],
                )

                if data_name == 'animation':
                    text = self.selection[-1]
                else:
                    text = self.selection
                self.select_text = tk.Label(self.controlpanel, text=text, fg=self.Colors['title1'],
                                            bg=self.Colors['extra'], font=self.Fonts['larger_title'])
                self.select_text.pack(pady=5)

                if self.selection == self.Scheduler_data[data_name]:
                    text = 'Используется'
                else:
                    text = ''

                need_install = False
                if data_name == 'font':
                    files = glob(f'Scheduler_Data/Fonts/{self.selection}/*.ttf')
                    if not all(FontManager.is_font_installed(i) for i in files):
                        if text:
                            text += ' '
                        text += '[Требуется установка]'
                        need_install = True
                self.info = tk.Label(self.controlpanel, text=text, fg=self.Colors['root_label'],
                                     bg=self.Colors['extra'], font=self.Fonts['small_title'])
                if need_install:
                    ToolTip(
                        self.info,
                        msg='Чтобы посмотреть этот шрифт, его необходимо установить в систему.\n'
                            'Выберите этот шрифт, чтобы установить его.',
                        delay=20, background=self.Colors['extra'], foreground=fg,
                        parent_kwargs={'bg': self.Colors['main']},
                        font=self.Fonts['text']
                    )
                self.info.pack(pady=5)

                if data_name in ('font', 'fontsize', 'theme'):
                    self.load_schedule(root=selector)
                    self.IN_SLEEP[0] = False
                    self.check_time(loop=False)
                    self.IN_SLEEP[0] = True
                elif data_name == 'animation':
                    if hasattr(self, 'animation'):
                        self.animation.stop()
                    self.update_animation(self.selection)
                    self.animation = self.RunAnimation(selector)
                    self.animation.start()

                selector['bg'] = self.Colors['extra']
                selector.update_idletasks()
                self.save_button = CreateButton(
                    selector, 'Сохранить', save,
                    default_kwargs={'bg': self.Colors['color1'], 'fg': self.Colors['title1'], 'r': 8, 'bd': 2,
                                    'bdr': 10, 'bdcolor': self.Colors['color1a']},
                    target_kwargs={'bg': self.Colors['color1a'], 'fg': self.Colors['title1'], 'offset': 0, 'bd': 2,
                                   'bdcolor': self.Colors['color1a']},
                    master_kwargs={'font': self.Fonts['larger_title'], 'width': selector.winfo_width(),
                                   'text_align': 'center',
                                   'place': {'method': 'pack', 'side': 'bottom', 'fill': 'x', 'expand': False}},
                    animation_kwargs=self.Values['animation_kwargs'],
                )
                WindowManager.SetToCenter(selector)

            match data_name:
                case 'font':
                    options = [os.path.basename(i).removesuffix('.dat') for i in
                               glob('Scheduler_Data/Fonts/*')]
                case 'fontsize':
                    options = [os.path.basename(i).removesuffix('.txt') for i in
                               glob('Scheduler_Data/FontSizes/*.txt')]
                case 'theme':
                    options = [os.path.basename(i).removesuffix('.txt') for i in
                               glob('Scheduler_Data/Themes/*.txt')]
                case 'animation':
                    options = (['Rotate'], ['Progressbar'],
                               *[['Handle', i] for i in
                                 [os.path.basename(i).removesuffix('.txt') for i in
                                  glob('Scheduler_Data/Animations/presets/*.txt')]],
                               *[['GIFPlayer', i] for i in
                                 [os.path.basename(i).removesuffix('.gif') for i in
                                  glob('Scheduler_Data/Animations/GIFs/*.gif')]])
                case _:
                    raise ValueError(f'Invalid data name \'{data_name}\'')

            self.delay = False
            self.selection = self.Scheduler_data[data_name]

            selector = WindowManager.CreateWindow(master=menu, title=f'Scheduler - Редактирование данных - {data_name}', bg=bg)
            selector.protocol('WM_DELETE_WINDOW', lambda: _quit(master=selector))
            selector.bind('<Escape>', lambda event: _quit(master=selector))
            selector.bind('<space>', save)
            selector.bind('<Return>', save)
            selector.bind('<Left>', _back)
            selector.bind('<Right>', _next)

            load_widgets()

            menu.withdraw()
            selector.focus_force()
            selector.mainloop()

            try:
                selector.destroy()
                menu.deiconify()
                menu.focus_force()
            except tk.TclError:
                pass

        """
        def edit_data(file, data_name):
            def write_new_data(i):
                self.NEW_DATA['EDITOR_DATA'][i] = items[i].get().strip()

            data = eval(open(f'Scheduler_Data/data/{file}.dat', 'r', encoding='utf-8').read())
            self.Scheduler_data['EDITOR_DATA'] = dict()
            self.NEW_DATA['EDITOR_DATA'] = dict()
            for i, j in data.items():
                self.Scheduler_data['EDITOR_DATA'][i] = j
                self.NEW_DATA['EDITOR_DATA'][i] = j
            self.EDITOR_FILE = file

            editor = CreateWindow(master=menu, title=f'Scheduler - Редактирование данных - {data_name}', bg=bg)
            editor.protocol('WM_DELETE_WINDOW', lambda: _quit(master=editor))
            editor.bind('<Escape>', lambda event: _quit(master=editor))
            editor.bind('<Return>', save)

            container = tk.Frame(editor, bd=0, bg=bg)
            canvas = tk.Canvas(container, height=700, highlightthickness=0, bg=bg)
            scrollbar = tk.Scrollbar(container, orient='vertical', command=canvas.yview)
            editorframe = tk.Frame(canvas, bg=bg, bd=0)
            editor.bind('<MouseWheel>', lambda event: on_mousewheel(event, canvas))
            editor.bind('<Up>', lambda event: canvas.yview_scroll(-2, 'units'))
            editor.bind('<Down>', lambda event: canvas.yview_scroll(2, 'units'))

            editorframe.bind(
                '<Configure>',
                lambda e: canvas.configure(
                    scrollregion=canvas.bbox('all')
                )
            )

            canvas.create_window((0, 0), window=editorframe, anchor='nw')
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.yview_moveto(0)

            container.pack(fill='both', expand=True)
            canvas.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            items = dict()
            for i, (j, k) in enumerate(data.items()):
                value = tk.StringVar(editor, value=k)
                items[j] = value
                frame = tk.LabelFrame(editorframe, text=j, bg=bg, fg=fg, font=self.Fonts['bigger_normal_title'])
                frame.grid(row=i, column=0, padx=5, pady=5, sticky='w')
                entry = tk.Entry(frame, textvariable=value, bg=bg, fg=fg, font=self.Fonts['normal_title'], insertbackground=fg, width=50)
                entry.bind('<KeyRelease>', lambda event, j=j: write_new_data(j))
                entry.grid(padx=10, pady=10, sticky='w')

            CreateButton(editor, text='Сохранить', bg=self.Colors['color1'], fg=fg,
                         font=self.Fonts['bigger_normal_title'], bd=0, height=1,
                         activebackground=self.Colors['color1a'], activeforeground=fg,
                         enterforeground=fg, enterbackground=self.Colors['color1a'],
                         command=save).pack(fill='x')

            editor.update()
            canvas['width'] = editorframe.winfo_width()

            PlaceWindow(editor, menu)
            menu.withdraw()
            editor.focus_force()
            editor.mainloop()

            try:
                editor.destroy()
                menu.deiconify()
                menu.focus_force()
            except tk.TclError:
                pass
        """

        def save(event=None, restart=True):
            if 'EDITOR_DATA' in self.NEW_DATA:
                if hasattr(self, 'EDITOR_FILE'):
                    open(f'Scheduler_Data/data/{self.EDITOR_FILE}.dat', 'w', encoding='utf-8').write(
                        str(self.NEW_DATA['EDITOR_DATA']))
                del self.NEW_DATA['EDITOR_DATA']
                del self.Scheduler_data['EDITOR_DATA']
            if self.Scheduler_data['font'] != self.NEW_DATA['font']:
                shutil.copy(f'Scheduler_Data/Fonts/{self.NEW_DATA["font"]}/{self.NEW_DATA["font"]}.dat',
                            f'Scheduler_Data/data/fonts.dat')
            if self.Scheduler_data['fontsize'] != self.NEW_DATA['fontsize']:
                shutil.copy(f'Scheduler_Data/FontSizes/{self.NEW_DATA["fontsize"]}.txt',
                            f'Scheduler_Data/data/fontsize.dat')
            if self.Scheduler_data['theme'] != self.NEW_DATA['theme']:
                shutil.copy(f'Scheduler_Data/Themes/{self.NEW_DATA["theme"]}.txt', f'Scheduler_Data/data/colors.dat')
                self.Colors = eval(open('Scheduler_Data/data/colors.dat', 'r', encoding='utf-8').read())

                images_config = eval(open('Scheduler_Data/data/images_config.dat', 'r', encoding='utf-8').read())
                for i, j in images_config.items():
                    change_image_color(f'Scheduler_Data/images/{i}', hex_to_rgb(j))

                hex1 = hex_to_rgb(self.Colors['title1'])
                hex2 = hex_to_rgb(self.Colors['extra'])

                create_animation_from_font('Scheduler_Data/Animations/Fonts/segoe_slboot.ttf',
                                           'Scheduler_Data/Animations/GIFs/winload.gif',
                                           fill=hex1, background=hex2)

            for i, j in self.NEW_DATA.items():
                self.Scheduler_data[i] = j
            open('Scheduler_Data/data/Scheduler_data.dat', 'w', encoding='utf-8').write(str(self.Scheduler_data))

            for i in self.TO_DELETE_SCHEDULES:
                os.remove(f'Scheduler_Data/Schedules/{i}.txt')
            if restart:
                self.root.attributes('-alpha', 0)
                menu.quit()
                self.root.after(0, self.restart)

        def _exit(event=None):
            save(restart=False)
            sys.exit()

        def _quit(event=None, master=None):
            if self.Scheduler_data != self.NEW_DATA or self.TO_DELETE_SCHEDULES:
                answer = askyesnocancel('Выход',
                                        'Для того, чтобы совершённые изменения вступили в силу, '
                                        'программе нужно перезапуститься.',
                                        master=master,
                                        yes_text='Сохранить и перезапустить',
                                        no_text='Отменить изменения', cancel_text='Остаться в меню',
                                        font=self.Fonts['smaller_title'], fg=self.Colors['title1'],
                                        bg=self.Colors['main'], animation_kwargs=self.Values['animation_kwargs'])
                if answer is None:
                    return
                if answer:
                    save()
                if not answer and master:
                    for i, j in self.Scheduler_data.items():
                        self.NEW_DATA[i] = j
                    self.offset = self.old_offset.copy()
                    shutil.copy(f'Scheduler_Data/Fonts/{self.Scheduler_data["font"]}/{self.Scheduler_data["font"]}.dat',
                                f'Scheduler_Data/data/fonts.dat')
                    shutil.copy(f'Scheduler_Data/FontSizes/{self.Scheduler_data["fontsize"]}.txt',
                                f'Scheduler_Data/data/fontsize.dat')
                    shutil.copy(f'Scheduler_Data/Themes/{self.Scheduler_data["theme"]}.txt',
                                f'Scheduler_Data/data/colors.dat')
                    self.update_colors()
                    self.update_fonts()
                    self.customStyle.theme_use(self.Scheduler_data['theme'])
                    master.quit()
            elif master:
                master.quit()

        menu.protocol('WM_DELETE_WINDOW', lambda: _quit(master=menu))
        menu.bind('<Escape>', lambda event: _quit(master=menu))
        menu.bind('<space>', lambda event: save())
        menu.bind('<Return>', lambda event: save())

        empty_img = tk.PhotoImage(file='Scheduler_Data/images/empty.png', master=menu)
        warning_img = tk.PhotoImage(file='Scheduler_Data/images/warning.png', master=menu)

        container = tk.Frame(menu, bd=0, bg=bg)
        canvas = tk.Canvas(container, highlightthickness=0, bg=bg)
        scrollbar = ttk.Scrollbar(container, orient='vertical')
        menuframe = tk.Frame(canvas, bg=bg, bd=0)

        menuframe.bind(
            '<Configure>',
            lambda e: canvas.configure(
                scrollregion=canvas.bbox('all')
            )
        )

        canvas.create_window((0, 0), window=menuframe, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.yview_moveto(0)

        container.pack(fill='both', expand=True)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        def create_menu_item(title='', description='', warning=False, type=None, **kwargs):
            mainframe = tk.Frame(menuframe, bg=bg)
            mainframe.pack(pady=8, fill='both', expand=True)
            leftframe = tk.Frame(mainframe, bg=bg)
            leftframe.pack(padx=20, side='left')
            rightframe = tk.Frame(mainframe, bg=bg)
            rightframe.pack(padx=20, side='right')

            info_width = 800 if type == 'toggle' else 500

            if title:
                tk.Label(leftframe, text=PlaceText(title, info_width, self.Fonts['bigger_title']), bg=bg, fg=fg,
                         font=self.Fonts['bigger_title'], justify='left').grid(sticky='w')
                if description:
                    tk.Label(leftframe, text=PlaceText(description, info_width, self.Fonts['text']), bg=bg, fg=fg,
                             font=self.Fonts['text'], justify='left').grid(sticky='w')
                warning_frame = tk.Frame(leftframe, bg=bg, highlightbackground=self.Colors['warning'],
                                         highlightthickness=warning)
                warning_frame.grid(padx=5, pady=5, sticky='w')
                warning_label = tk.Label(warning_frame, text=' Изменяйте, если знаете, что делаете!',
                                         image=(empty_img, warning_img)[warning], compound='left', bg=bg,
                                         fg=(bg, self.Colors['warning'])[warning], font=self.Fonts['text'])
                if warning:
                    ToolTip(
                        warning_label,
                        msg='Совершайте изменения здесь только в том случае, если Вы знаете, что делаете.\n'
                            'Неверные действия могут сделать работу программы некорректной.',
                        delay=0, background=bg, foreground=fg,
                        parent_kwargs={'bg': self.Colors['warning']},
                        font=self.Fonts['text']
                    )
                    warning_label.grid(padx=2, pady=2)
                else:
                    warning_label.place()

            mainframe.update_idletasks()
            height = mainframe.winfo_height()

            match type:
                case 'separator':
                    color = kwargs['color'] if 'color' in kwargs else fg
                    thickness = kwargs['thickness'] if 'thickness' in kwargs else 2
                    height = kwargs['height'] if 'height' in kwargs else 2
                    text = kwargs['text'] if 'text' in kwargs else ''
                    separator = tk.Frame(mainframe, bg=bg, highlightbackground=color, highlightthickness=thickness,
                                         height=height)
                    separator.pack(padx=20, pady=30, fill='both', expand=True)
                    label = tk.Label(mainframe, text=PlaceText(text, 800, self.Fonts['bigger_title']), bg=bg, fg=color,
                                     font=self.Fonts['bigger_title'])
                    label.place(relx=0.5, rely=0.4, anchor='center')
                    leftframe.destroy()
                    rightframe.destroy()
                    return mainframe

                case 'button':
                    text = kwargs['text'] if 'text' in kwargs else ''
                    color = kwargs['color'] if 'color' in kwargs else fg
                    font = kwargs['font'] if 'font' in kwargs else self.Fonts['big_title']
                    command = kwargs['command'] if 'command' in kwargs else None
                    event = kwargs['event'] if 'event' in kwargs else False
                    button = CreateButton(
                        rightframe, PlaceText(text, 340, font), command, event,
                        default_kwargs={'bg': bg, 'fg': fg, 'r': 8, 'bd': 2, 'bdr': 10, 'bdcolor': color},
                        target_kwargs={'bg': color, 'fg': bg, 'offset': 0, 'bd': 2, 'bdcolor': color},
                        master_kwargs={'font': font, 'width': 350, 'height': height,
                                       'text_align': 'center', 'padx': 0, 'pady': 0,
                                       'place': {'method': 'pack', 'side': None, 'fill': 'both', 'expand': True}},
                        animation_kwargs=self.Values['animation_kwargs'],
                    )
                    return button

                case 'toggle':
                    def on_click():
                        if checkbox.state is None:
                            self.NEW_DATA[data_key] = not self.NEW_DATA[data_key]
                            checkbox.configure('in', master_kwargs={'image': checkbox_images[self.NEW_DATA[data_key]]})
                        else:
                            if checkbox.state:
                                checkbox.off_command()
                                checkbox.configure('in', master_kwargs={'image': checkbox_images[0]})
                            else:
                                checkbox.on_command()
                                checkbox.configure('in', master_kwargs={'image': checkbox_images[1]})
                            checkbox.state = not checkbox.state

                    data_key = kwargs['data_key'] if 'data_key' in kwargs else None
                    state = kwargs['state'] if 'state' in kwargs else None
                    on_command = kwargs['on_command'] if 'on_command' in kwargs else None
                    off_command = kwargs['off_command'] if 'off_command' in kwargs else None
                    if data_key is None:
                        image = checkbox_images[state]
                    else:
                        image = checkbox_images[self.NEW_DATA[data_key]]
                    color = kwargs['color'] if 'color' in kwargs else self.Colors['main']
                    checkbox = CreateButton(
                        rightframe, None, on_click,
                        default_kwargs={'bg': bg, 'r': 8, 'bd': 2, 'bdr': 10, 'bdcolor': color},
                        target_kwargs={'bg': color, 'offset': 0, 'bd': 2, 'bdcolor': color},
                        master_kwargs={'image': image, 'padx': 0, 'pady': 0, 'ipadx': 0, 'ipady': 0,
                                       'place': {'method': 'pack', 'side': None, 'fill': 'both', 'expand': True}},
                        animation_kwargs=self.Values['animation_kwargs'],
                    )
                    checkbox.state = state
                    checkbox.on_command = on_command
                    checkbox.off_command = off_command
                    return checkbox

                case 'combobox':
                    options = kwargs['options'] if 'options' in kwargs else []
                    if isinstance(options, list | tuple):
                        options = {i: i for i in options}
                    keys = tuple(options.keys())
                    values = tuple(options.values())
                    data_key = kwargs['data_key'] if 'data_key' in kwargs else None
                    data_type = kwargs['data_type'] if 'data_type' in kwargs else str

                    combobox = ttk.Combobox(rightframe, values=keys, font=self.Fonts['big_title'],
                                            state='readonly', width=22)
                    combobox.get_value = lambda: data_type(combobox.get())

                    if data_key in self.Scheduler_data:
                        element = self.Scheduler_data[data_key]
                        if element not in values:
                            return
                        index = values.index(element)
                        combobox.set(keys[index])

                    if data_key:
                        def on_select(event=None):
                            value = combobox.get_value()
                            if value not in options:
                                return
                            self.NEW_DATA[data_key] = options[value]
                    else:
                        def on_select(event=None):
                            pass
                    combobox.on_select = on_select

                    def on_mouse_wheel(event):
                        def return_back_value():
                            combobox.set(prev_value)
                            on_select(event)

                        prev_value = combobox.get_value()
                        combobox.after(0, return_back_value)

                    combobox.bind('<MouseWheel>', on_mouse_wheel)
                    combobox.bind('<<ComboboxSelected>>', on_select)
                    combobox.pack(fill='both', expand=True)
                    return combobox

                case _:
                    raise ValueError(f'Invalid menu item type: {type}')

        def delete_schedule():
            schedule = ScheduleCombobox.get_value()
            if not askyesno('Удаление расписания',
                            f'Вы действительно хотите удалить расписание \'{schedule}\'?',
                            menu, fg=self.Colors['title1'], bg=self.Colors['main'],
                            font=self.Fonts['smaller_title'], yes_deiconify=True,
                            animation_kwargs=self.Values['animation_kwargs']):
                return
            values = ScheduleCombobox['values']
            ScheduleCombobox['values'] = tuple(i for i in values if i != schedule)
            if len(values) > 1:
                index = values.index(schedule) + 1
                if index >= len(values):
                    index = 0
                to_set = values[index]
            else:
                to_set = ''
            ScheduleCombobox.set(to_set)
            ScheduleCombobox.on_select()
            self.TO_DELETE_SCHEDULES.append(schedule)

        create_menu_item(type='separator', text='Внешний вид')
        create_menu_item(title='Шрифт',
                         description='Выберите для себя наиболее красивый шрифт!',
                         type='button', text='Выбрать шрифт', color=self.Colors['color5a'], startfade=True,
                         command=lambda: choose_data('font'))
        create_menu_item(title='Размер шрифта',
                         description='Выберите для себя наиболее удобный размер шрифта!',
                         type='button', text='Выбрать размер', color=self.Colors['color2a'], startfade=True,
                         command=lambda: choose_data('fontsize'))
        create_menu_item(title='Тема',
                         description='Выберите для себя наиболее привлекательную тему!',
                         type='button', text='Выбрать тему', color=self.Colors['color5a'], startfade=True,
                         command=lambda: choose_data('theme'))

        create_menu_item(title='Анимация загрузки',
                         description='Выберите для себя наиболее занимательную анимацию!',
                         type='button', text='Выбрать анимацию', color=self.Colors['color2a'], startfade=True,
                         command=lambda: choose_data('animation'))
        create_menu_item(type='separator', text='Расписание')
        create_menu_item(title='Создание расписания',
                         description='Создайте новое расписание',
                         type='button', text='Создать расписание', color=self.Colors['color5a'], startfade=True,
                         command=lambda: self.create_schedule(master=menu))
        ScheduleCombobox = create_menu_item(title='Выбор расписания',
                                            description='Выберите своё расписание из имеющихся на устройстве',
                                            type='combobox', options=tuple(
                i.removeprefix('Scheduler_Data/Schedules/').removesuffix('.txt') for i in
                glob('Scheduler_Data/Schedules/*.txt')),
                                            data_key='current_schedule')
        create_menu_item(title='Изменение расписания',
                         description='Измените выбранное расписание',
                         type='button', text='Изменить расписание', color=self.Colors['color2a'], startfade=True,
                         command=lambda: self.create_schedule(master=menu, schedule=self.NEW_DATA['current_schedule']))
        create_menu_item(title='Удаление расписания',
                         description='Удалите выбранное расписание',
                         type='button', text='Удалить расписание', color=self.Colors['color4a'], startfade=True,
                         command=delete_schedule)
        create_menu_item(type='separator', text='Производительность')
        create_menu_item(title='Качество анимаций',
                         description='Настройте качество анимаций в интерфейсе программы '
                                     'под мощность своего устройства. '
                                     'Снизьте качество, если во время проигрывания анимаций '
                                     'Ваше устройство начинает тормозить',
                         type='combobox', options={'Моментально': 0.01,
                                                   'Прерывисто': 0.1,
                                                   'Плавно': 0.3,
                                                   'Плавнее': 0.5,
                                                   'Очень плавно': 1.0},
                         data_key='animation_quality')
        create_menu_item(type='separator', text='Параметры')
        create_menu_item(title='Ярлык',
                         description='Разместить ярлык программы на рабочем столе для быстрого доступа к ней',
                         type='toggle', state=os.path.exists(f'C:/Users/{getuser()}/Desktop/Scheduler.lnk'),
                         on_command=lambda: ShortcutCreator('Scheduler.exe').create(name='Scheduler',
                                                                                    description='Планировщик'),
                         off_command=lambda: os.remove(f'C:/Users/{getuser()}/Desktop/Scheduler.lnk'))
        create_menu_item(title='Разрешение изменения размера окна',
                         description='Позволить окну расписания изменение размера окна',
                         type='toggle', data_key='root_resizable')
        create_menu_item(title='Спящий режим',
                         description='Позволить окну расписания автоматически переходить в спящий режим',
                         type='toggle', data_key='set_in_sleep')
        create_menu_item(title='Округление времени в большую сторону',
                         description='Округлять время в большую сторону, а не в меньшую',
                         type='toggle', data_key='ceil_time')
        create_menu_item(type='separator', text='Время')
        create_menu_item(title='Программное время',
                         description='Посмотрите текущее время, используемое в программе',
                         type='button', text='Посмотреть время', color=self.Colors['color5a'],
                         command=lambda: self.show_current_time(master=menu))
        create_menu_item(title='Смещение времени',
                         description='Настройте смещение времени',
                         type='button', text='Настроить смещение', color=self.Colors['color2a'],
                         command=lambda: self.show_current_time(master=menu, offset=True))
        create_menu_item(title='Использовать время сервера',
                         description='Позволить программе получать время с сервера. Потребуется интернет-подключение',
                         type='toggle', data_key='use_time_server')
        create_menu_item(title='Временной сервер',
                         description='Укажите адрес временного сервера, с которого программа будет получать время',
                         type='combobox', options=(
                'pool.ntp.org', '0.pool.ntp.org', '1.pool.ntp.org', '2.pool.ntp.org', '3.pool.ntp.org',
                'time.windows.com'
            ), data_key='time_server')
        create_menu_item(title='Интервал синхронизации времени',
                         description='Укажите интервал синхронизации времени с сервером в секундах',
                         type='combobox', options=(5, 10, 20, 30, 60, 120, 180, 300),
                         data_key='time_sync_interval', data_type=int)
        create_menu_item(type='separator', text='Управление')
        create_menu_item(title='О программе',
                         description='Откройте справку о программе Scheduler',
                         type='button', text='Открыть', color=self.Colors['color5a'],
                         command=lambda: self.about(menu))
        create_menu_item(title='Целостность программы',
                         description='Проверьте целостность программы, чтобы выявить возможные причины её некорректной работы',
                         type='button', text='Проверить', color=self.Colors['color2a'],
                         command=lambda: self.integrity_check(master=menu, showinfo=True))
        create_menu_item(title='Перезапуск',
                         description='Сохраните изменения и запустите программу повторно.\n'
                                     'Это может помочь в случае неисправности в работе программы',
                         type='button', text='Перезапустить', color=self.Colors['color3a'],
                         command=save)
        create_menu_item(title='Выход',
                         description='Сохраните изменения и завершите работу программы',
                         type='button', text='Выйти', color=self.Colors['color4a'],
                         command=_exit)

        canvas.configure(width=menuframe.winfo_width(), height=min(menuframe.winfo_height(), 700))
        menu.update_idletasks()

        if menuframe.winfo_height() > canvas.winfo_height():
            scrollbar.configure(command=canvas.yview)
            menu.bind('<MouseWheel>', lambda event: WindowManager.on_mousewheel(event, canvas))
            menu.bind('<Up>', lambda event: canvas.yview_scroll(-2, 'units'))
            menu.bind('<Down>', lambda event: canvas.yview_scroll(2, 'units'))

        CreateButton(
            menu, 'Применить изменения', save,
            default_kwargs={'bg': self.Colors['color1'], 'fg': fg, 'r': 8, 'bd': 2, 'bdr': 10,
                            'bdcolor': self.Colors['color1a']},
            target_kwargs={'bg': self.Colors['color1a'], 'fg': fg, 'offset': 0, 'bd': 2,
                           'bdcolor': self.Colors['color1a']},
            master_kwargs={'font': self.Fonts['bigger_title'], 'width': menu.winfo_width(),
                           'text_align': 'center',
                           'place': {'method': 'pack', 'side': 'bottom', 'fill': 'x', 'expand': False}},
            animation_kwargs=self.Values['animation_kwargs'],
        )

        master_state = self.root.state()
        WindowManager.PlaceWindow(menu, master)
        menu.attributes('-alpha', 1)
        menu.focus_force()
        menu.mainloop()

        if self.RESTART:
            return
        if master == self.root and master_state == 'zoomed':
            self.root.state('zoomed')

        menu.destroy()
        master.deiconify()
        master.focus_force()
        self.load_schedule(ShowLoadingAnimation=False)

    def show_current_time(self, master=None, offset=False):
        def update_time(resync=False, set_after=True):
            self.get_time_now(resync=resync)
            infolabel.configure(text=f"{self.now.strftime('%d.%m.%Y')} / {self.now.strftime('%H:%M:%S')}\n"
                                     f"{self.WEEKNAMES[self.now.weekday()]}, {self.now.day} {self.MONTHNAMES2[self.now.month - 1]}")
            if set_after:
                timewin.after(1000, update_time)

        def setminsize():
            timewin.update_idletasks()
            if self.minwidth < timewin.winfo_width():
                self.minwidth = timewin.winfo_width()
            if self.minheight < timewin.winfo_height():
                self.minheight = timewin.winfo_height()
            timewin.minsize(self.minwidth, self.minheight)

        def _quit(event=None):
            timewin.quit()
            timewin.destroy()
            master.deiconify()

        def set_offset(new_offset):
            for i, j in self.offset.items():
                self.offset[i] += new_offset[i]
                offset_widgets[i].configure(text=self.offset[i])
            self.NEW_DATA['offset'] = self.offset
            update_time(resync=True, set_after=False)

        if master is None:
            master = self.root

        self.minwidth = 0
        self.minheight = 0

        timewin = WindowManager.CreateWindow(master=master, title='Текущее время', bg=self.Colors['extra'], resizable=(True, True))
        timewin.protocol('WM_DELETE_WINDOW', _quit)
        timewin.bind('<Escape>', _quit)

        infoframe = tk.Frame(timewin, bg=self.Colors['extra'])
        infoframe.pack(anchor='center', expand=True, fill='both')

        infolabel = tk.Label(infoframe, font=self.Fonts['larger_title'],
                             fg=self.Colors['title1'], bg=self.Colors['extra'])
        infolabel.pack(anchor='center', expand=True, fill='both', padx=10, pady=10)
        if offset:
            offsetframe = tk.Frame(infoframe, bg=self.Colors['extra'])
            offsetframe.pack(anchor='center', expand=True, fill='both', padx=10, pady=10)

            CreateButton(
                offsetframe, '↑', lambda: set_offset({'hours': 1, 'minutes': 0, 'seconds': 0}),
                default_kwargs={'bg': self.Colors['extra'], 'fg': self.Colors['title1'], 'r': 8, 'bd': 2, 'bdr': 10,
                                'bdcolor': self.Colors['color1']},
                target_kwargs={'bg': self.Colors['color1a'], 'fg': self.Colors['title1'], 'offset': 0, 'bd': 2,
                               'bdcolor': self.Colors['color1a']},
                master_kwargs={'font': self.Fonts['bigger_title'],
                               'text_align': 'center',
                               'place': {'method': 'grid', 'row': 0, 'column': 0}},
                animation_kwargs=self.Values['animation_kwargs'],
            )
            CreateButton(
                offsetframe, '↑', lambda: set_offset({'hours': 0, 'minutes': 1, 'seconds': 0}),
                default_kwargs={'bg': self.Colors['extra'], 'fg': self.Colors['title1'], 'r': 8, 'bd': 2, 'bdr': 10,
                                'bdcolor': self.Colors['color1']},
                target_kwargs={'bg': self.Colors['color1a'], 'fg': self.Colors['title1'], 'offset': 0, 'bd': 2,
                               'bdcolor': self.Colors['color1a']},
                master_kwargs={'font': self.Fonts['bigger_title'],
                               'text_align': 'center',
                               'place': {'method': 'grid', 'row': 0, 'column': 1}},
                animation_kwargs=self.Values['animation_kwargs'],
            )
            CreateButton(
                offsetframe, '↑', lambda: set_offset({'hours': 0, 'minutes': 0, 'seconds': 1}),
                default_kwargs={'bg': self.Colors['extra'], 'fg': self.Colors['title1'], 'r': 8, 'bd': 2, 'bdr': 10,
                                'bdcolor': self.Colors['color1']},
                target_kwargs={'bg': self.Colors['color1a'], 'fg': self.Colors['title1'], 'offset': 0, 'bd': 2,
                               'bdcolor': self.Colors['color1a']},
                master_kwargs={'font': self.Fonts['bigger_title'],
                               'text_align': 'center',
                               'place': {'method': 'grid', 'row': 0, 'column': 2}},
                animation_kwargs=self.Values['animation_kwargs'],
            )

            hours_offset = tk.Label(offsetframe, text=self.offset['hours'], font=self.Fonts['bigger_title'],
                                    bg=self.Colors['extra'], fg=self.Colors['title1'])
            hours_offset.grid(row=1, column=0, padx=5, pady=5)
            minutes_offset = tk.Label(offsetframe, text=self.offset['minutes'], font=self.Fonts['bigger_title'],
                                      bg=self.Colors['extra'], fg=self.Colors['title1'])
            minutes_offset.grid(row=1, column=1, padx=5, pady=5)
            seconds_offset = tk.Label(offsetframe, text=self.offset['seconds'], font=self.Fonts['bigger_title'],
                                      bg=self.Colors['extra'], fg=self.Colors['title1'])
            seconds_offset.grid(row=1, column=2, padx=5, pady=5)

            CreateButton(
                offsetframe, '↓', lambda: set_offset({'hours': -1, 'minutes': 0, 'seconds': 0}),
                default_kwargs={'bg': self.Colors['extra'], 'fg': self.Colors['title1'], 'r': 8, 'bd': 2, 'bdr': 10,
                                'bdcolor': self.Colors['color4']},
                target_kwargs={'bg': self.Colors['color4a'], 'fg': self.Colors['title1'], 'offset': 0, 'bd': 2,
                               'bdcolor': self.Colors['color4a']},
                master_kwargs={'font': self.Fonts['bigger_title'],
                               'text_align': 'center',
                               'place': {'method': 'grid', 'row': 2, 'column': 0}},
                animation_kwargs=self.Values['animation_kwargs'],
            )
            CreateButton(
                offsetframe, '↓', lambda: set_offset({'hours': 0, 'minutes': -1, 'seconds': 0}),
                default_kwargs={'bg': self.Colors['extra'], 'fg': self.Colors['title1'], 'r': 8, 'bd': 2, 'bdr': 10,
                                'bdcolor': self.Colors['color4']},
                target_kwargs={'bg': self.Colors['color4a'], 'fg': self.Colors['title1'], 'offset': 0, 'bd': 2,
                               'bdcolor': self.Colors['color4a']},
                master_kwargs={'font': self.Fonts['bigger_title'],
                               'text_align': 'center',
                               'place': {'method': 'grid', 'row': 2, 'column': 1}},
                animation_kwargs=self.Values['animation_kwargs'],
            )
            CreateButton(
                offsetframe, '↓', lambda: set_offset({'hours': 0, 'minutes': 0, 'seconds': -1}),
                default_kwargs={'bg': self.Colors['extra'], 'fg': self.Colors['title1'], 'r': 8, 'bd': 2, 'bdr': 10,
                                'bdcolor': self.Colors['color4']},
                target_kwargs={'bg': self.Colors['color4a'], 'fg': self.Colors['title1'], 'offset': 0, 'bd': 2,
                               'bdcolor': self.Colors['color4a']},
                master_kwargs={'font': self.Fonts['bigger_title'],
                               'text_align': 'center',
                               'place': {'method': 'grid', 'row': 2, 'column': 2}},
                animation_kwargs=self.Values['animation_kwargs'],
            )

            offset_widgets = {'seconds': seconds_offset, 'minutes': minutes_offset, 'hours': hours_offset}

        update_time()
        setminsize()

        WindowManager.PlaceWindow(timewin, master)
        timewin.focus_force()
        timewin.attributes('-topmost', True)
        timewin.mainloop()

    def create_schedule(self, master=None, schedule=None, bg=None, fg=None):
        if master is None:
            master = self.initialize
        if bg is None:
            bg = self.Colors['extra']
        if fg is None:
            fg = self.Colors['title1']

        if schedule is None:
            while True:
                self.schedule_name = sanitize_filename(askstring('Имя расписания',
                                                                 'Выберите имя для расписания',
                                                                 master=master, no_deiconify=False,
                                                                 font=self.Fonts['smaller_title'],
                                                                 fg=self.Colors['title1'],
                                                                 bg=self.Colors['main'],
                                                                 animation_kwargs=self.Values['animation_kwargs']))
                if self.schedule_name is None:
                    master.deiconify()
                    return -1
                self.schedule_name = self.schedule_name.strip()
                if not self.schedule_name:
                    master.deiconify()
                    return -1
                if f'Scheduler_Data/Schedules/{self.schedule_name}.txt' not in glob(
                        'Scheduler_Data/Schedules/*.txt') or askyesno('Имена совпадают',
                                                                      'Расписание с таким именем уже существует.\nВы хотите перезаписать его?',
                                                                      master=master,
                                                                      font=self.Fonts['smaller_title'],
                                                                      fg=self.Colors['title1'],
                                                                      bg=self.Colors['main'],
                                                                      animation_kwargs=self.Values['animation_kwargs']):
                    break
        else:
            self.schedule_name = schedule

        title = f'Scheduler - Создание расписания - {self.schedule_name}' if schedule is None else f'Scheduler - Изменение расписания - {self.schedule_name}'
        win = WindowManager.CreateWindow(master=master, title=title, bg=bg)

        container = tk.Frame(win, bd=0, bg=bg)
        canvas = tk.Canvas(container, bg=bg, width=910, height=600, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient='vertical')
        frame = tk.Frame(canvas, bg=bg, bd=0)

        frame.bind(
            '<Configure>',
            lambda e: canvas.configure(
                scrollregion=canvas.bbox('all')
            )
        )

        canvas.create_window((0, 0), window=frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.yview_moveto(0)

        container.pack(fill='both', expand=True)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        add_img = tk.PhotoImage(file='Scheduler_Data/images/add.png')
        del_img = tk.PhotoImage(file='Scheduler_Data/images/delete.png')
        up_img = tk.PhotoImage(file='Scheduler_Data/images/up.png')
        down_img = tk.PhotoImage(file='Scheduler_Data/images/down.png')
        mark_img = tk.PhotoImage(file='Scheduler_Data/images/mark.png')

        self.sched = []
        self.weeks = []
        self.weekitems = []

        self.NEW_CHANGES = False

        def create_item(i, lesson_name='', duration=None, mark=''):
            def next_item(i, num, item):
                if item == 'sttime':
                    self.sched[i][num]['nddurentry'].focus()
                    return

                indx = ('lessonentry', 'stdurentry')[item == 'ndtime']
                nextnum = self.sched[i][num]['nmbr'].num + 1
                for j in self.sched[i].values():
                    if j['nmbr'].num == nextnum:
                        j[indx].focus()
                        break
                else:
                    for j in range(i + 1, 7):
                        if len(self.sched[j]) > 0:
                            for k in range(9):
                                if k in self.sched[j].keys():
                                    self.sched[j][k][indx].focus()
                                    break
                            else:
                                continue
                            break
                    else:
                        for j in range(0, i):
                            if len(self.sched[j]) > 0:
                                for k in range(9):
                                    if k in self.sched[j].keys():
                                        self.sched[j][k][indx].focus()
                                        break
                                else:
                                    continue
                                break
                        else:
                            for j in self.sched[i].values():
                                if j['nmbr'].num == 1:
                                    j[indx].focus()
                                    break

            def check_entry(entry, strvar):
                def format_time(time):
                    stdur = ''
                    length = 0
                    for i in time:
                        if i.isdigit():
                            stdur += i
                            length += 1
                            if length == 4:
                                break

                    if length <= 2:
                        stdur += '00'

                    length = len(stdur)
                    if length == 1:
                        hours = int(stdur)
                        minutes = 0
                    elif length == 2:
                        hours = int(stdur[0])
                        minutes = int(stdur[1])
                    elif length == 3:
                        hours = int(stdur[0])
                        minutes = int(stdur[1:])
                    else:
                        hours = int(stdur[:2])
                        minutes = int(stdur[2:])

                    if hours >= 24:
                        hours = 23
                    if minutes >= 60:
                        minutes = 59

                    return f'{hours}:{minutes:02d}'

                def router(strvar):
                    strvar.set(format_time(strvar.get()) if self.EDIT else self.OLD_VALUE)

                def on_key_release(strvar):
                    self.EDIT = strvar.get().strip() != ''

                self.OLD_VALUE = strvar.get()
                self.EDIT = False
                entry.delete(0, 'end')
                entry.bind('<KeyRelease>', lambda event, strvar=strvar: on_key_release(strvar))
                entry.bind('<FocusOut>', lambda event, strvar=strvar: router(strvar))

            def delete_item(event, i, num):
                if self.sched[i][num]['nmbr'].num == 0:
                    nextnum = self.sched[i][num]['nmbr'].num + 1
                    for j in self.sched[i].values():
                        if j['nmbr'].num == nextnum:
                            j['up_button'].configure('out', master_kwargs={'state': 'disabled'})
                            break
                elif self.sched[i][num]['nmbr'].num == len(self.sched[i]) - 1:
                    nextnum = self.sched[i][num]['nmbr'].num - 1
                    for j in self.sched[i].values():
                        if j['nmbr'].num == nextnum:
                            j['down_button'].configure('out', master_kwargs={'state': 'disabled'})
                            break

                for j in self.sched[i][num].values():
                    if hasattr(j, 'destroy'):
                        j.destroy()
                self.sched[i].pop(num)

                self.weeks[i]['spinbox'].configure(to=min(10 - len(self.sched[i]), 9))
                for j, k in enumerate(self.sched[i].values()):
                    k['mainframe'].grid(row=j + 1, column=0, padx=5, pady=5, sticky='nesw')
                    k['nmbr'].setnum(j)
                self.weeks[i]['add_button'].configure('out', master_kwargs={'state': 'normal'})

            def move_item(event, i, num, direction):
                nextnum = self.sched[i][num]['nmbr'].num + (1 if direction == 'down' else -1)
                for j in self.sched[i].values():
                    if j['nmbr'].num == nextnum:
                        if event.state != 12:
                            a, b = self.sched[i][num]['lesson'].get(), j['lesson'].get()
                            j['lesson'].set(a)
                            self.sched[i][num]['lesson'].set(b)
                        if event.state in (9, 12):
                            c, d, e, f = self.sched[i][num]['stdur'].get(), j['stdur'].get(), self.sched[i][num][
                                'nddur'].get(), j['nddur'].get()
                            j['stdur'].set(c)
                            self.sched[i][num]['stdur'].set(d)
                            j['nddur'].set(e)
                            self.sched[i][num]['nddur'].set(f)
                        break

            def mark_item(event, i, num, mark):
                nmbr = self.sched[i][num]['nmbr']
                if nmbr.mark == mark:
                    mark = ''
                nmbr.mark = mark
                nmbr.setnum(nmbr.num)

            def on_focus(entry, strvar):
                def create_history(entry, strvar):
                    def get_entry_value_with_insert(entry):
                        value = entry.get()
                        insert = entry.index('insert')
                        value = value[:insert] + '<<<INSERT>>>' + value[insert:]
                        return value

                    def add_to_history(entry):
                        def history_append(entry, what):
                            value = get_entry_value_with_insert(entry)
                            if len(self.history) == 0 or what not in (self.history[-1], value):
                                self.history.append(what)

                        what = get_entry_value_with_insert(entry)
                        if len(self.history) >= self.history_limit:
                            self.history.pop(0)
                        entry.after(0, lambda entry=entry, what=what: history_append(entry, what))

                    def set_from_history(entry, strvar):
                        def history_append(entry, strvar, what_to_set):
                            if self.redo_value is not None and abs(len(self.redo_value) - len(what_to_set)) == 1:
                                self.redo_history.append(self.redo_value)
                            self.redo_value = what_to_set

                            strvar.set(what_to_set.replace('<<<INSERT>>>', ''))
                            entry.icursor(what_to_set.find('<<<INSERT>>>'))

                        if len(self.history) == 0:
                            return
                        what_to_set = self.history.pop()

                        if len(self.redo_history) >= self.redo_limit:
                            self.redo_history.pop(0)
                        if len(self.redo_history) == 0:
                            self.redo_history.append(get_entry_value_with_insert(entry))
                        entry.after(0, lambda entry=entry, strvar=strvar, what_to_set=what_to_set: history_append(entry,
                                                                                                                  strvar,
                                                                                                                  what_to_set))

                    def redo_from_history(entry, strvar):
                        def history_append(entry, strvar, what_to_set):
                            if self.history_value is not None and abs(len(self.history_value) - len(what_to_set)) == 1:
                                self.history.append(self.history_value)
                            self.history_value = what_to_set

                            strvar.set(what_to_set.replace('<<<INSERT>>>', ''))
                            entry.icursor(what_to_set.find('<<<INSERT>>>'))

                        if len(self.redo_history) == 0:
                            return
                        what_to_set = self.redo_history.pop()

                        if len(self.history) >= self.history_limit:
                            self.history.pop(0)
                        if len(self.history) == 0:
                            self.history.append(get_entry_value_with_insert(entry))
                        entry.after(0, lambda entry=entry, strvar=strvar, what_to_set=what_to_set: history_append(entry,
                                                                                                                  strvar,
                                                                                                                  what_to_set))

                    value = get_entry_value_with_insert(entry)
                    self.history = [value]
                    self.history_value = None
                    self.history_limit = 100
                    self.redo_history = []
                    self.redo_value = None
                    self.redo_limit = 100
                    entry.bind('<KeyPress>', lambda event, entry=entry: add_to_history(entry))
                    entry.bind('<<Undo>>', lambda event, entry=entry, strvar=strvar: set_from_history(entry, strvar))
                    entry.bind('<<Redo>>', lambda event, entry=entry, strvar=strvar: redo_from_history(entry, strvar))

                create_history(entry, strvar)
                entry.select_range(0, 'end')

            def setnum(n):
                nmbr.num = n
                nmbr.configure(text=str(n + self.weeks[i]['spinbox'].getnum()) + nmbr.mark)

            num = 0
            while True:
                if num not in self.sched[i].keys():
                    break
                num += 1

            bg = self.Colors['main']

            mainframe = tk.Frame(self.weeks[i]['weekframe'], bg=bg, bd=1, relief='raised')
            mainframe.grid(row=num + 1, column=0, padx=5, pady=5, sticky='nesw')

            nmbr = tk.Label(mainframe, bg=bg, fg=fg, font=self.Fonts['big_title'], width=2, justify='left', anchor='w')
            nmbr.mark = mark
            nmbr.setnum = setnum
            nmbr.grid(row=0, column=0, padx=5, pady=5, sticky='nesw')

            lesson = tk.StringVar(win, value=lesson_name)
            lessonentry = tk.Entry(mainframe, textvariable=lesson, bg=bg, fg=fg, insertbackground=fg,
                                   font=self.Fonts['big_title'], width=24)
            lessonentry.bind('<Return>', lambda event, i=i, num=num: next_item(i, num, 'lesson'))
            lessonentry.bind('<FocusIn>', lambda event, entry=lessonentry, strvar=lesson: on_focus(entry, strvar))
            lessonentry.grid(row=0, column=1, padx=5, pady=5, sticky='nesw')

            durframe = tk.Frame(mainframe, bg=bg, bd=0)
            durframe.grid(row=0, column=2, padx=20, pady=5, sticky='nesw')

            stdur = tk.StringVar(win, value='00:00' if duration is None else duration.split('-')[0])
            stdurentry = tk.Entry(durframe, textvariable=stdur, bg=bg, fg=fg, insertbackground=fg,
                                  font=self.Fonts['big_title'], width=5)
            stdurentry.bind('<Return>', lambda event, i=i, num=num: next_item(i, num, 'sttime'))
            stdurentry.bind('<FocusIn>', lambda event, entry=stdurentry, strvar=stdur: check_entry(entry, stdur))
            stdurentry.grid(row=0, column=0, padx=5, pady=5, sticky='nesw')

            dash = tk.Label(durframe, text='-', bg=bg, fg=fg, font=self.Fonts['big_title'])
            dash.grid(row=0, column=1, padx=5, pady=5, sticky='nesw')

            nddur = tk.StringVar(win, value='00:00' if duration is None else duration.split('-')[1])
            nddurentry = tk.Entry(durframe, textvariable=nddur, bg=bg, fg=fg, insertbackground=fg,
                                  font=self.Fonts['big_title'], width=5)
            nddurentry.bind('<Return>', lambda event, i=i, num=num: next_item(i, num, 'ndtime'))
            nddurentry.bind('<FocusIn>', lambda event, entry=nddurentry, strvar=nddur: check_entry(entry, nddur))
            nddurentry.grid(row=0, column=2, padx=5, pady=5, sticky='nesw')

            mainframe.update_idletasks()
            height = mainframe.winfo_height()

            up_button = CreateButton(
                mainframe, None, lambda event: move_item(event, i, num, 'up'), True,
                default_kwargs={'bg': self.Colors['color2'], 'r': 8, 'bd': 2, 'bdr': 10,
                                'bdcolor': self.Colors['main'], 'disabled_bg': self.Colors['main'],
                                'disabled_bdcolor': self.Colors['shade2']},
                target_kwargs={'bg': self.Colors['color2a'], 'disabled_bg': self.Colors['extra'], 'offset': 0, 'bd': 2,
                               'bdcolor': self.Colors['color2a'], 'disabled_bdcolor': self.Colors['shade2']},
                master_kwargs={'image': up_img, 'height': height,
                               'place': {'method': 'grid', 'row': 0, 'column': 3}},
                animation_kwargs=self.Values['animation_kwargs'],
            )
            up_button.color = self.Colors['color2a']

            down_button = CreateButton(
                mainframe, None, lambda event: move_item(event, i, num, 'down'), True,
                default_kwargs={'bg': self.Colors['color3'], 'r': 8, 'bd': 2, 'bdr': 10,
                                'bdcolor': self.Colors['main'], 'disabled_bg': self.Colors['main'],
                                'disabled_bdcolor': self.Colors['shade2']},
                target_kwargs={'bg': self.Colors['color3a'], 'disabled_bg': self.Colors['extra'], 'offset': 0, 'bd': 2,
                               'bdcolor': self.Colors['color3a'], 'disabled_bdcolor': self.Colors['shade2']},
                master_kwargs={'image': down_img, 'height': height, 'state': 'disabled',
                               'place': {'method': 'grid', 'row': 0, 'column': 4}},
                animation_kwargs=self.Values['animation_kwargs'],
            )
            down_button.color = self.Colors['color3a']

            mark_button = CreateButton(
                mainframe, None, lambda event: mark_item(event, i, num, '*'), True,
                default_kwargs={'bg': self.Colors['color1'], 'r': 8, 'bd': 2, 'bdr': 10,
                                'bdcolor': self.Colors['main']},
                target_kwargs={'bg': self.Colors['color1a'], 'disabled_bg': self.Colors['extra'], 'offset': 0, 'bd': 2,
                               'bdcolor': self.Colors['color1a']},
                master_kwargs={'image': mark_img, 'height': height, 'place': {'method': 'grid', 'row': 0, 'column': 5}},
                animation_kwargs=self.Values['animation_kwargs'],
            )
            mark_button.color = self.Colors['color1a']

            del_button = CreateButton(
                mainframe, None, lambda event: delete_item(event, i, num), True,
                default_kwargs={'bg': self.Colors['color4'],
                                'r': 8, 'bd': 2, 'bdr': 10, 'bdcolor': self.Colors['main']},
                target_kwargs={'bg': self.Colors['color4a'],
                               'offset': 0, 'bd': 2, 'bdcolor': self.Colors['color4a']},
                master_kwargs={'image': del_img, 'height': height,
                               'place': {'method': 'grid', 'row': 0, 'column': 6}},
                animation_kwargs=self.Values['animation_kwargs'],
            )
            del_button.color = self.Colors['color4a']

            self.sched[i][num] = {'mainframe': mainframe, 'nmbr': nmbr, 'lesson': lesson, 'lessonentry': lessonentry,
                                  'stdurentry': stdurentry, 'nddurentry': nddurentry, 'up_button': up_button,
                                  'down_button': down_button, 'mark_button': mark_button, 'del_button': del_button,
                                  'durframe': durframe, 'dash': dash, 'stdur': stdur, 'nddur': nddur}

            child = []
            for j in self.sched[i][num].values():
                if not hasattr(j, 'keys'):
                    if hasattr(j, 'canvas'):
                        j.FadeEffectInCommand = lambda obj=j, val=j.color: obj.configure('out', default_kwargs={
                            'bdcolor': val})
                        j.FadeEffectOutCommand = lambda obj=j: obj.configure('out', default_kwargs={
                            'bdcolor': self.Colors['main']})
                        child.append(j)
                    continue
                if 'bg' in j.keys():
                    child.append(j)

            FadeEffect(mainframe, self.Colors['shade2'], child=child, **self.Values['animation_kwargs'])

            for j, k in enumerate(self.sched[i].values()):
                k['mainframe'].grid(row=j + 1, column=0, padx=5, pady=5, sticky='nesw')
                k['nmbr'].setnum(j)
            sched_length = len(self.sched[i])
            self.weeks[i]['spinbox'].configure(to=min(10 - sched_length, 9))
            if sched_length == 1:
                self.sched[i][num]['up_button'].configure('out', master_kwargs={'state': 'disabled'})

            else:
                nextnum = self.sched[i][num]['nmbr'].num - 1
                for j in self.sched[i].values():
                    if j['nmbr'].num == nextnum:
                        j['down_button'].configure('out', master_kwargs={'state': 'normal'})
                        break

            if sched_length + self.weeks[i]['spinbox'].getnum() == 10:
                self.weeks[i]['add_button'].configure('out', master_kwargs={'state': 'disabled'})
            down_button.configure('out', master_kwargs={'state': 'disabled'})
            lessonentry.focus()

        def quit(event=None, save=False):
            def write_data():
                subjects = []
                duration = []
                startfrom = []
                mark = []
                for i in range(7):
                    week = self.sched[i]
                    sub = []
                    dur = []
                    m = []
                    for j in range(min(len(week), 9)):
                        for g, k in week.items():
                            if k['nmbr'].num == j:
                                break
                        sub.append(week[g]['lesson'].get().strip())
                        dur.append(f'{week[g]['stdurentry'].get()}-{week[g]['nddurentry'].get()}')
                        m.append(week[g]['nmbr'].mark)
                    subjects.append(tuple(sub))
                    duration.append(tuple(dur))
                    startfrom.append(self.weeks[i]['spinbox'].getnum())
                    mark.append(tuple(m))

                self.new_schedule = {'subjects': tuple(subjects), 'duration': tuple(duration),
                                     'startfrom': tuple(startfrom), 'mark': tuple(mark)}

                edited = schedule is None or self.new_schedule != eval(
                    open(f'Scheduler_Data/Schedules/{schedule}.txt', 'r', encoding='utf-8').read())
                if not save and edited:
                    answer = askyesnocancel('Выход', 'Совершённые изменения не были сохранены.',
                                            master=win,
                                            yes_text='Сохранить изменения', no_text='Отменить изменения',
                                            cancel_text='Остаться в редакторе',
                                            font=self.Fonts['smaller_title'], fg=self.Colors['title1'],
                                            bg=self.Colors['main'], animation_kwargs=self.Values['animation_kwargs'])
                    if answer is None:
                        return
                    if not answer:
                        win.quit()
                        return
                if edited:
                    open(f'Scheduler_Data/Schedules/{self.schedule_name}.txt', 'w', encoding='utf-8').write(
                        str(self.new_schedule))
                    self.NEW_CHANGES = True
                win.quit()

            win.focus()
            win.after(0, write_data)

        def startfrom_select(i):
            for j, k in enumerate(self.sched[i].values()):
                k['nmbr'].setnum(j)
            if len(self.sched[i]) + self.weeks[i]['spinbox'].getnum() == 10:
                self.weeks[i]['add_button'].configure('out', master_kwargs={'state': 'disabled'})
            else:
                self.weeks[i]['add_button'].configure('out', master_kwargs={'state': 'normal'})

        for i, j in enumerate(self.WEEKNAMES):
            weekframe = tk.LabelFrame(frame, bg=bg, fg=fg, text=j, font=self.Fonts['bigger_title'])
            weekframe.grid(padx=5, pady=5, sticky='nesw')
            add_button = CreateButton(
                weekframe, None, lambda i=i: create_item(i),
                default_kwargs={'bg': self.Colors['main'], 'disabled_bg': self.Colors['extra'],
                                'r': 8, 'bd': 2, 'bdr': 10, 'bdcolor': self.Colors['shade2'],
                                'disabled_bdcolor': self.Colors['shade2']},
                target_kwargs={'bg': self.Colors['shade2'], 'disabled_bg': self.Colors['extra'],
                               'offset': 0, 'bd': 2,
                               'bdcolor': self.Colors['shade2'], 'disabled_bdcolor': self.Colors['main']},
                master_kwargs={'width': 893, 'height': 42, 'image': add_img,
                               'place': {'method': 'grid', 'row': 100, 'column': 0, 'sticky': 'nesw'}},
                animation_kwargs=self.Values['animation_kwargs'],
            )
            startfrom_frame = tk.Frame(weekframe, bg=bg, bd=1, relief='raised')
            startfrom_frame.grid(row=0, column=0, padx=5, pady=5, sticky='nesw')
            tk.Label(startfrom_frame, text='Начинать нумерацию с:', bg=bg, fg=fg,
                     font=self.Fonts['smaller_title']).grid(row=0, column=0, padx=5, pady=5, sticky='nesw')
            var = tk.StringVar(win, value='1')
            spinbox = tk.Spinbox(startfrom_frame, textvariable=var,
                                 from_=0, to=9, width=2,
                                 bg=self.Colors['title1'], fg=self.Colors['extra'], font=self.Fonts['smaller_title'],
                                 justify='center', state='readonly')
            spinbox.getnum = lambda obj=spinbox: int(obj.get())
            spinbox.configure(command=lambda i=i: startfrom_select(i))
            spinbox.grid(row=0, column=1, padx=5, pady=5, sticky='nesw')
            self.weeks.append({'weekframe': weekframe, 'add_button': add_button, 'spinbox': spinbox, 'var': var})
            self.sched.append(dict())

        if schedule:
            data = eval(open(f'Scheduler_Data/Schedules/{schedule}.txt', 'r', encoding='utf-8').read())
            for i in range(len(data['subjects'])):
                week = data['subjects'][i]
                self.weeks[i]['var'].set(data['startfrom'][i])
                for j in range(len(week)):
                    create_item(i, data['subjects'][i][j], data['duration'][i][j], data['mark'][i][j])

        win.update_idletasks()
        if frame.winfo_height() > canvas.winfo_height():
            scrollbar.configure(command=canvas.yview)
            win.bind('<MouseWheel>', lambda event: WindowManager.on_mousewheel(event, canvas))
            win.bind('<Up>', lambda event: canvas.yview_scroll(-2, 'units'))
            win.bind('<Down>', lambda event: canvas.yview_scroll(2, 'units'))

        text = 'Создать расписание' if schedule is None else 'Изменить расписание'
        CreateButton(
            win, text, lambda: quit(save=True),
            default_kwargs={'bg': self.Colors['color1'], 'r': 8, 'bd': 2, 'bdr': 10, 'bdcolor': self.Colors['color1a']},
            target_kwargs={'bg': self.Colors['color1a'], 'offset': 0, 'bd': 2, 'bdcolor': self.Colors['color1a']},
            master_kwargs={'font': self.Fonts['bigger_title'], 'text_align': 'center', 'width': win.winfo_width(),
                           'place': {'method': 'pack', 'fill': 'x'}},
            animation_kwargs=self.Values['animation_kwargs'],
        )

        win.protocol('WM_DELETE_WINDOW', quit)
        win.bind('<Escape>', quit)
        master_state = self.root.state()
        WindowManager.PlaceWindow(win, master)
        win.focus_force()
        win.mainloop()
        if master == self.root and master_state == 'zoomed':
            self.root.state('zoomed')

        if self.NEW_CHANGES:
            master.after(0, self.restart)
            return True, self.schedule_name
        win.destroy()
        master.deiconify()
        master.focus_force()
        return -1

    def about(self, master):
        def _quit(event=None):
            aboutwin.destroy()
            master.deiconify()
            WindowManager.OnTopWindow(master)

        aboutwin = WindowManager.CreateWindow(master, 'О программе Scheduler', bg=self.Colors['main'])
        aboutwin.protocol('WM_DELETE_WINDOW', _quit)
        aboutwin.bind('<Escape>', _quit)

        CreateButton(
            aboutwin,
            default_kwargs={'bg': self.Colors['main'], 'r': 8, 'bdr': 10, 'bd': 2, 'bdcolor': self.Colors['main']},
            target_kwargs={'bg': self.Colors['shade2'], 'bd': 2, 'bdcolor': self.Colors['extra']},
            master_kwargs={'image': self.images['Scheduler64'], 'width': 110, 'height': 110, 'padx': 10, 'pady': 10,
                           'place': {'method': 'grid', 'row': 0, 'column': 0, 'rowspan': 2, 'sticky': 'nesw'}},
            animation_kwargs=self.Values['animation_kwargs'],
        )

        tk.Label(aboutwin, text=f'Scheduler {__version__}', bg=self.Colors['main'], fg=self.Colors['title1'],
                 font=self.Fonts['huge_title']).grid(row=0, column=1, padx=10, pady=5)
        tk.Label(aboutwin, text='Copyright © 2025-2026 Малухин Мирон. Все права защищены.', bg=self.Colors['main'],
                 fg=self.Colors['title1'], font=self.Fonts['text']).grid(row=1, column=1, padx=10, pady=5)

        WindowManager.PlaceWindow(aboutwin, master)
        aboutwin.mainloop()

    def set_view(self, view):
        self.view = view
        self.new_view = True

    def restart(self):
        if hasattr(self, 'last_after'):
            self.root.after_cancel(self.last_after)
        self.RESTART = True
        self.root.quit()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


class FadeEffect:
    def __init__(self, widget, target_bg, target_fg=None, startfade=False, delay=5, in_steps=20, out_steps=80,
                 child=None):
        self.root = widget.master
        self.widget = widget
        self.default_bg = widget.cget('bg')
        if target_fg is not None:
            self.default_fg = widget.cget('fg')
        else:
            self.default_fg = None
        self.target_bg = target_bg
        self.target_fg = target_fg
        self.delay = delay
        self.in_steps = in_steps
        self.out_steps = out_steps

        if child is None:
            child_base = None
            child_canvas = None
        else:
            child_base = [i for i in child if not hasattr(i, 'canvas')]
            child_canvas = [i for i in child if hasattr(i, 'canvas')]
        self.child_base = child_base
        self.child_canvas = child_canvas

        widget.bind('<Enter>', self.fade_in)
        widget.bind('<Leave>', self.fade_out)

        if startfade:
            widget.config(bg=target_bg, fg=target_fg)
            self.fade_out()

    def fade_in(self, event=None):
        """Плавное изменение цветов к указанному значению."""
        self.start_fade(self.widget, self.target_bg, self.target_fg, self.delay, self.in_steps)
        if self.child_base is not None:
            for i in self.child_base:
                self.start_fade(i, self.target_bg, self.target_fg, self.delay, self.in_steps)
        if self.child_canvas is not None:
            for i in self.child_canvas:
                if not hasattr(i, 'FadeEffectInCommand'):
                    continue
                i.FadeEffectInCommand()

    def fade_out(self, event=None):
        # Получаем текущие координаты курсора
        x, y = self.root.winfo_pointerxy()
        # Получаем виджет, над которым сейчас курсор
        widget = self.root.winfo_containing(x, y)

        # Если курсор не внутри виджета или его дочерних элементов
        if widget is not None and (
                widget == self.widget or widget.winfo_parent() == self.widget.winfo_pathname(self.widget.winfo_id())):
            return
        self.start_fade(self.widget, self.default_bg, self.default_fg, self.delay, self.out_steps)
        if self.child_base is not None:
            for i in self.child_base:
                self.start_fade(i, self.default_bg, self.default_fg, self.delay, self.out_steps)
        if self.child_canvas is not None:
            for i in self.child_canvas:
                if not hasattr(i, 'FadeEffectOutCommand'):
                    continue
                i.FadeEffectOutCommand()

    def start_fade(self, widget, target_bg, target_fg, delay, max_steps):
        if hasattr(widget, 'after_id'):
            widget.after_cancel(widget.after_id)
        self._fade_effect(widget, target_bg, target_fg, delay, max_steps, 0)

    def _fade_effect(self, widget, target_bg, target_fg, delay, max_steps, current_step):
        if current_step >= max_steps:
            widget.config(bg=target_bg, fg=target_fg)
            return

        # Получаем текущие цвета в RGB (0-65535)
        w = widget.winfo_toplevel()
        current_bg = widget.cget('bg')

        br1, bg1, bb1 = w.winfo_rgb(current_bg)
        br2, bg2, bb2 = w.winfo_rgb(target_bg)

        progress = current_step / max_steps

        new_br = int(br1 + (br2 - br1) * progress)
        new_bg = int(bg1 + (bg2 - bg1) * progress)
        new_bb = int(bb1 + (bb2 - bb1) * progress)

        # Преобразуем в hex (#RRGGBB)
        new_bg_color = f'#{new_br // 256:02x}{new_bg // 256:02x}{new_bb // 256:02x}'

        if self.default_fg is not None:
            current_fg = widget.cget('fg')

            fr1, fg1, fb1 = w.winfo_rgb(current_fg)
            fr2, fg2, fb2 = w.winfo_rgb(target_fg)

            new_fr = int(fr1 + (fr2 - fr1) * progress)
            new_fg = int(fg1 + (fg2 - fg1) * progress)
            new_fb = int(fb1 + (fb2 - fb1) * progress)

            new_fg_color = f'#{new_fr // 256:02x}{new_fg // 256:02x}{new_fb // 256:02x}'

            widget.config(fg=new_fg_color)

        widget.config(bg=new_bg_color)

        widget.after_id = widget.after(delay, self._fade_effect, widget, target_bg, target_fg, delay, max_steps,
                                       current_step + 1)


class ToolTip:
    def __init__(
            self,
            widget,
            msg,
            delay=500,
            parent_kwargs=None,
            **message_kwargs
    ):
        self.widget = widget
        self.text = msg
        self.delay = delay  # Задержка перед появлением (в мс)
        self.parent_kwargs = parent_kwargs or {}
        self.message_kwargs = message_kwargs
        self.tip_window = None
        self.id = None

        # Стандартные параметры для родительского окна (можно переопределить через parent_kwargs)
        self.default_parent_kwargs = {
            'master': self.widget,  # Окно, которое будет родителем для всплывающего окна
            'bg': '#ffffe0',  # Цвет фона окна подсказки
            'padx': 1,  # Отступы по X
            'pady': 1,  # Отступы по Y
            'ipadx': 10,  # Внутренние отступы по X
            'ipady': 10,  # Внутренние отступы по Y
        }

        # Стандартные параметры для Label (можно переопределить через message_kwargs)
        self.default_message_kwargs = {
            'background': '#ffffe0',  # Цвет фона текста
            'foreground': 'black',  # Цвет текста
            'font': ('Arial', 10),
            'relief': 'solid',
            'borderwidth': 0,
            'anchor': 'center',
            'justify': 'left',
            'xoffset': 15,
            'yoffset': 15
        }

        # Объединяем стандартные и пользовательские параметры
        self.parent_kwargs = {**self.default_parent_kwargs, **self.parent_kwargs}
        self.message_kwargs = {**self.default_message_kwargs, **self.message_kwargs}

        font = self.message_kwargs['font']
        temp_font = tk.font.Font(font=font)
        text_lines = [i for i in msg.split('\n')]
        lines_lengths = [len(i) for i in text_lines]
        max_length = max(lines_lengths)
        index_of_max = lines_lengths.index(max_length)
        max_line = text_lines[index_of_max]
        text_measure = temp_font.measure(max_line)
        self.text_width = text_measure + self.parent_kwargs['ipadx'] * 2

        # Привязываем события
        self.widget.bind('<Enter>', self.schedule_tooltip)
        self.widget.bind('<Leave>', self.hide_tooltip)
        self.widget.bind('<Destroy>', lambda e: self.hide_tooltip())

    def schedule_tooltip(self, event=None):
        self.cancel_scheduled_tooltip()
        self.id = self.widget.after(self.delay, self.show_tooltip)

    def cancel_scheduled_tooltip(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def show_tooltip(self):
        if self.tip_window or not self.text:
            return

        # Позиционирование подсказки
        x, y = self.widget.winfo_pointerxy()
        x += self.message_kwargs['xoffset']
        y += self.message_kwargs['yoffset']
        if x + self.text_width >= self.widget.winfo_screenwidth():
            x -= self.text_width + self.message_kwargs['xoffset'] * 2

        # Создаем окно подсказки с настройками из parent_kwargs
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)  # Убираем рамку и заголовок
        self.tip_window.wm_geometry(f'+{x}+{y}')

        # Применяем parent_kwargs (например, bg, padx, pady)
        for key, value in self.parent_kwargs.items():
            try:
                self.tip_window[key] = value
            except tk.TclError:
                pass  # Игнорируем некорректные параметры

        # Создаем Label с настройками из message_kwargs
        label = ttk.Label(
            self.tip_window,
            text=self.text,
            **{
                k: v for k, v in self.message_kwargs.items()
                if k in ('background', 'foreground', 'font', 'relief', 'borderwidth', 'anchor', 'justify')
            }
        )
        label.pack(**{
            k: v for k, v in self.parent_kwargs.items()
            if k in ('padx', 'pady', 'ipadx', 'ipady')
        })

    def hide_tooltip(self, event=None):
        if event is not None:
            # Получаем текущие координаты курсора
            x, y = event.widget.master.master.winfo_pointerxy()
            # Получаем виджет, над которым сейчас курсор
            widget = event.widget.master.master.winfo_containing(x, y)

            # Если курсор не внутри виджета или его дочерних элементов
            if widget is not None and widget == self.parent_kwargs['master']:
                return

        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None
        self.cancel_scheduled_tooltip()


class ShortcutCreator:
    """
    Универсальный класс для создания ярлыков на разных ОС
    """

    def __init__(self, target_path: str):
        """
        Инициализация с целевым путем

        Args:
            target_path: Путь к файлу или папке для которой создается ярлык
        """
        self.target_path = os.path.abspath(target_path)
        self.system = sys.platform
        self.shortcut_extension = self._get_shortcut_extension()

        if not os.path.exists(self.target_path):
            raise FileNotFoundError(f'Целевой путь не существует: {self.target_path}')

    def _get_shortcut_extension(self) -> str:
        """Возвращает расширение для ярлыка в зависимости от ОС"""
        if self.system == 'win32':
            return '.lnk'
        elif self.system == 'darwin':  # macOS
            return '.app'
        elif self.system == 'linux':
            return '.desktop'
        else:
            return '.shortcut'

    def create(self,
               shortcut_path=None,
               name=None,
               description: str = '',
               working_dir=None,
               icon_path=None) -> bool:
        """
        Создает ярлык

        Args:
            shortcut_path: Полный путь для сохранения ярлыка
            name: Имя ярлыка (без расширения)
            description: Описание ярлыка
            working_dir: Рабочая директория
            icon_path: Путь к иконке

        Returns:
            bool: True если успешно, False если ошибка
        """
        # Определяем путь по умолчанию
        if shortcut_path is None:
            shortcut_path = self._get_default_shortcut_path(name)

        # Определяем рабочую директорию
        if working_dir is None:
            working_dir = os.path.dirname(self.target_path)

        try:
            if self.system == 'Windows':
                return self._create_windows_shortcut(shortcut_path, description, working_dir, icon_path)
            elif self.system == 'Darwin':
                return self._create_macos_shortcut(shortcut_path, name, description, icon_path)
            elif self.system == 'Linux':
                return self._create_linux_shortcut(shortcut_path, description, icon_path)
            else:
                print(f'Неподдерживаемая платформа: {self.system}')
                return False

        except Exception as e:
            print(f'Ошибка при создании ярлыка: {e}')
            return False

    def _get_default_shortcut_path(self, name=None) -> str:
        """Возвращает путь по умолчанию для ярлыка"""
        if name is None:
            name = f'{Path(self.target_path).stem} Shortcut'

        if self.system == 'Windows':
            desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
        else:
            desktop = os.path.join(os.path.expanduser('~'), 'Desktop')

        return os.path.join(desktop, f'{name}{self.shortcut_extension}')

    def _create_windows_shortcut(self, shortcut_path: str, description: str,
                                 working_dir: str, icon_path) -> bool:
        """Создание ярлыка для Windows"""
        try:
            import pythoncom
            from win32com.client import Dispatch

            pythoncom.CoInitialize()
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.Targetpath = self.target_path
            shortcut.Description = description
            shortcut.WorkingDirectory = working_dir

            if icon_path and os.path.exists(icon_path):
                shortcut.IconLocation = icon_path

            shortcut.save()
            pythoncom.CoUninitialize()

            print(f'✓ Windows ярлык создан: {shortcut_path}')
            return True

        except ImportError:
            print('✗ Установите pywin32: pip install pywin32')
            return False
        except Exception as e:
            print(f'✗ Ошибка Windows: {e}')
            return False

    def _create_macos_shortcut(self, shortcut_path: str, name,
                               description: str, icon_path) -> bool:
        """Создание ярлыка для macOS"""
        try:
            if name is None:
                name = Path(self.target_path).stem

            # Создаем структуру .app bundle
            app_path = Path(shortcut_path)
            contents_dir = app_path / 'Contents'
            macos_dir = contents_dir / 'MacOS'
            resources_dir = contents_dir / 'Resources'

            # Очищаем существующий bundle
            if app_path.exists():
                shutil.rmtree(app_path)

            # Создаем директории
            macos_dir.mkdir(parents=True, exist_ok=True)
            resources_dir.mkdir(parents=True, exist_ok=True)

            # Создаем исполняемый скрипт
            executable_name = name.replace(' ', '_')
            executable_script = macos_dir / executable_name

            with open(executable_script, 'w') as f:
                f.write(f"""#!/bin/bash
open "{self.target_path}"
""")

            # Делаем скрипт исполняемым
            executable_script.chmod(0o755)

            # Копируем иконку если указана
            if icon_path and os.path.exists(icon_path):
                icon_ext = Path(icon_path).suffix
                shutil.copy2(icon_path, resources_dir / f'icon{icon_ext}')

            # Создаем Info.plist
            plist_data = {
                'CFBundleName': name,
                'CFBundleExecutable': executable_name,
                'CFBundleIdentifier': f'com.shortcut.{executable_name}',
                'CFBundleVersion': '1.0',
                'CFBundleShortVersionString': '1.0',
                'CFBundlePackageType': 'APPL',
                'CFBundleSignature': 'shct',
                'CFBundleGetInfoString': description,
            }

            with open(contents_dir / 'Info.plist', 'wb') as f:
                plistlib.dump(plist_data, f)

            print(f'✓ macOS ярлык создан: {shortcut_path}')
            return True

        except Exception as e:
            print(f'✗ Ошибка macOS: {e}')
            return False

    def _create_linux_shortcut(self, shortcut_path: str, description: str,
                               icon_path) -> bool:
        """Создание .desktop файла для Linux"""
        try:
            icon_line = f'Icon={icon_path}\n' if icon_path and os.path.exists(icon_path) else 'Icon=\n'

            desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={Path(self.target_path).stem} Shortcut
Comment={description}
Exec=xdg-open "{self.target_path}"
{icon_line}Terminal=false
Categories=Utility;
"""

            with open(shortcut_path, 'w', encoding='utf-8') as f:
                f.write(desktop_content)

            os.chmod(shortcut_path, 0o755)
            print(f'✓ Linux ярлык создан: {shortcut_path}')
            return True

        except Exception as e:
            print(f'✗ Ошибка Linux: {e}')
            return False

    def create_alias(self, alias_path=None) -> bool:
        """
        Создает символическую ссылку (алиас)
        Работает на macOS и Linux
        """
        if self.system not in ['Darwin', 'Linux']:
            print('✗ Символические ссылки поддерживаются только на macOS и Linux')
            return False

        if alias_path is None:
            desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
            alias_path = os.path.join(desktop, f'{Path(self.target_path).stem} Alias')

        try:
            if os.path.exists(alias_path):
                os.remove(alias_path)

            os.symlink(self.target_path, alias_path)
            print(f'✓ Символическая ссылка создана: {alias_path}')
            return True
        except Exception as e:
            print(f'✗ Ошибка создания ссылки: {e}')
            return False

    def get_system_info(self) -> dict:
        """Возвращает информацию о системе"""
        return {
            'system': self.system,
            'target_path': self.target_path,
            'shortcut_extension': self.shortcut_extension,
            'target_exists': os.path.exists(self.target_path),
            'is_file': os.path.isfile(self.target_path),
            'is_directory': os.path.isdir(self.target_path)
        }


class CanvasAnimation:
    def __init__(self, parent, text=None, bind=None,
                 default_kwargs=None, target_kwargs=None, master_kwargs=None, animation_kwargs=None):
        self.parent = parent
        self.text = text
        self.bind = bind
        default_kwargs = default_kwargs or {}
        target_kwargs = target_kwargs or {}
        master_kwargs = master_kwargs or {}
        animation_kwargs = animation_kwargs or {}

        self.base_default_kwargs = {
            'bg': 'black',
            'fg': 'white',
            'disabled_bg': None,
            'disabled_fg': None,
            'disabled_bd': None,
            'disabled_bdr': None,
            'disabled_bdcolor': None,
            'decoration_measure': None,
            'underline_width': 0,
            'strike_width': 0,
            'hidden_fg': None,
            'hidden_coords': [None, None],
            'offset': 0,
            'r': 0,
            'bdr': 0,
            'bd': 0,
            'bdcolor': 'black'
        }
        self.base_target_kwargs = {
            'bg': None,
            'fg': None,
            'disabled_bg': None,
            'disabled_fg': None,
            'disabled_bd': None,
            'disabled_bdr': None,
            'disabled_bdcolor': None,
            'decoration_measure': None,
            'underline_width': 0,
            'strike_width': 0,
            'hidden_fg': None,
            'hidden_coords': [None, None],
            'offset': 10,
            'r': 20,
            'bdr': 24,
            'bd': 0,
            'bdcolor': 'white'
        }
        self.base_master_kwargs = {
            'state': 'normal',
            'font': ('Arial', 12),
            'image': None,
            'hidden_text': None,
            'hidden_font': None,
            'width': None,
            'height': None,
            'text_align': 'left',
            'padx': 5,
            'pady': 5,
            'ipadx': 10,
            'ipady': 5,
            'place': None
        }
        self.base_animation_kwargs = {
            'decoration_exponent_up': 1.5,
            'decoration_exponent_down': 1,
            'hidden_x_exponent_up': 2,
            'hidden_x_exponent_down': 1,
            'delay': 5,
            'in_steps': 20,
            'out_steps': 80
        }

        # Объединяем стандартные и пользовательские параметры
        self.default_kwargs = {**self.base_default_kwargs, **default_kwargs}
        self.target_kwargs = {**self.base_target_kwargs, **target_kwargs}
        self.master_kwargs = {**self.base_master_kwargs, **master_kwargs}
        self.animation_kwargs = {**self.base_animation_kwargs, **animation_kwargs}

        if self.target_kwargs['fg'] is None:
            self.target_kwargs['fg'] = self.default_kwargs['fg']
        if self.target_kwargs['bg'] is None:
            self.target_kwargs['bg'] = self.default_kwargs['bg']

        if self.default_kwargs['disabled_bg'] is None:
            self.default_kwargs['disabled_bg'] = self.default_kwargs['bg']
        if self.default_kwargs['disabled_fg'] is None:
            self.default_kwargs['disabled_fg'] = self.default_kwargs['fg']
        if self.default_kwargs['disabled_bd'] is None:
            self.default_kwargs['disabled_bd'] = self.default_kwargs['bd']
        if self.default_kwargs['disabled_bdr'] is None:
            self.default_kwargs['disabled_bdr'] = self.default_kwargs['bdr']
        if self.default_kwargs['disabled_bdcolor'] is None:
            self.default_kwargs['disabled_bdcolor'] = self.default_kwargs['bdcolor']
        if self.target_kwargs['disabled_bg'] is None:
            self.target_kwargs['disabled_bg'] = self.target_kwargs['bg']
        if self.target_kwargs['disabled_fg'] is None:
            self.target_kwargs['disabled_fg'] = self.target_kwargs['fg']
        if self.target_kwargs['disabled_bd'] is None:
            self.target_kwargs['disabled_bd'] = self.target_kwargs['bd']
        if self.target_kwargs['disabled_bdr'] is None:
            self.target_kwargs['disabled_bdr'] = self.target_kwargs['bdr']
        if self.target_kwargs['disabled_bdcolor'] is None:
            self.target_kwargs['disabled_bdcolor'] = self.target_kwargs['bdcolor']

        if self.default_kwargs['hidden_fg'] is None:
            self.default_kwargs['hidden_fg'] = self.default_kwargs['bg']
        if self.target_kwargs['hidden_fg'] is None:
            self.target_kwargs['hidden_fg'] = self.target_kwargs['fg']
        if self.master_kwargs['hidden_font'] is None:
            self.master_kwargs['hidden_font'] = self.master_kwargs['font']

        self.tasks = []

        if isinstance(parent, tk.Canvas):
            self.canvas = parent
        else:
            self._create_canvas(self.default_kwargs)

        self.disabled_default_kwargs = {i: self.default_kwargs[i] for i in self.default_kwargs.keys() if
                                        not i.startswith('disabled_')}
        self.disabled_target_kwargs = {i: self.target_kwargs[i] for i in self.target_kwargs.keys() if
                                       not i.startswith('disabled_')}
        for i in ('fg', 'bg', 'bd', 'bdr', 'bdcolor'):
            self.disabled_default_kwargs[i] = self.default_kwargs[f'disabled_{i}']
            self.disabled_target_kwargs[i] = self.target_kwargs[f'disabled_{i}']

        self.canvas.toplevel = self.canvas.winfo_toplevel()

        place = self.master_kwargs['place']
        if place is None:
            return
        kwargs = {i: j for i, j in place.items() if i != 'method'}
        if place['method'] == 'pack':
            self.canvas.pack(padx=self.master_kwargs['padx'], pady=self.master_kwargs['pady'], **kwargs)
        elif place['method'] == 'grid':
            self.canvas.grid(padx=self.master_kwargs['padx'], pady=self.master_kwargs['pady'], **kwargs)
        elif place['method'] == 'place':
            self.canvas.place(padx=self.master_kwargs['padx'], pady=self.master_kwargs['pady'], **kwargs)
        else:
            raise ValueError(
                f'Неизвестный метод размещения: {place["method"]}. '
                'Допустимые методы: pack, grid, place'
            )

        self.canvas.bind('<Enter>', lambda event: self.animate_in(event, True))
        self.canvas.bind('<Leave>', lambda event: self.animate_out(event, True))

    def _create_canvas(self, transition_kwargs):
        self.canvas = tk.Canvas(self.parent, bg=self.parent['bg'], highlightthickness=0)

        self._update_size()
        self._update_canvas(self.lines, transition_kwargs)

        return self.canvas

    def _update_size(self):
        default_kwargs = self.default_kwargs
        default_hidden_coords = default_kwargs['hidden_coords']
        target_kwargs = self.target_kwargs
        decoration_measure = target_kwargs['decoration_measure']
        target_hidden_coords = target_kwargs['hidden_coords']
        target_offset = target_kwargs['offset']

        master_kwargs = self.master_kwargs
        font = master_kwargs['font']
        image = master_kwargs['image']
        width = master_kwargs['width']
        height = master_kwargs['height']
        padx = master_kwargs['padx']
        ipadx = master_kwargs['ipadx']
        ipady = master_kwargs['ipady']

        self.temp_font = tk.font.Font(font=font)
        self.linespace = self.temp_font.metrics('linespace')
        self.middle = self.temp_font.metrics('ascent') / 2 + self.temp_font.metrics('descent')

        if image is None:
            self.image_size = (0, 0)
        else:
            self.image_size = image.width(), image.height()

        # Получаем размеры текста
        if self.text is None:
            if width is None:
                text_width = 0
            else:
                text_width = width - padx * 2 - ipadx * 2 - target_offset - self.image_size[0]
            self.lines = []
        elif width is None:
            # Если максимальная ширина не задана, используем ширину текста
            text_width = self.temp_font.measure(self.text)
            self.lines = [self.text]
        else:
            text_width = width - padx * 2 - ipadx * 2 - target_offset - self.image_size[0]
            self.lines = PlaceText(self.text, width - target_offset - padx * 2 - ipadx * 2 - self.image_size[0],
                                   font=self.temp_font).split('\n')

        if height is None:
            text_height = self.linespace * len(self.lines)
        else:
            text_height = height - padx * 2 - ipady * 2

        self.canvas.width = text_width + ipadx * 2 + target_offset + self.image_size[0]
        self.canvas.height = max(text_height + ipady * 2, self.image_size[1])
        self.canvas.configure(
            width=self.canvas.width,
            height=self.canvas.height
        )

        self._update_decoration_measure()

        if self.bind is not None:
            for i, j, k in self.bind:
                if k:
                    self.canvas.bind(i,
                                     lambda event, f=j: f(event) if self.master_kwargs['state'] == 'normal' else None)
                else:
                    self.canvas.bind(i, lambda event, f=j: f() if self.master_kwargs['state'] == 'normal' else None)

        if default_hidden_coords[0] is None:
            self.default_kwargs['hidden_coords'][0] = -target_offset
        if default_hidden_coords[1] is None:
            self.default_kwargs['hidden_coords'][1] = ipady
        if target_hidden_coords[0] is None:
            self.target_kwargs['hidden_coords'][0] = target_offset / 2
        if target_hidden_coords[1] is None:
            self.target_kwargs['hidden_coords'][1] = ipady

        decoration_measure = self.target_kwargs['decoration_measure']
        if self.image_size[0] > 0:
            ipadx *= 2
        match self.master_kwargs['text_align']:
            case 'left':
                self._get_text_x = lambda i: ipadx + self.image_size[0]
            case 'center':
                self._get_text_x = lambda i: self.canvas.width / 2 - decoration_measure[i] / 2
            case 'right':
                self._get_text_x = lambda i: self.canvas.width - ipadx - decoration_measure[i]
            case _:
                raise ValueError('text_align должен быть "center", "left" или "right"')

        if height is None:
            self._get_text_y = lambda i: ipady + i * self.linespace
        else:
            num_lines = len(self.lines)
            if num_lines == 0:
                return
            if num_lines == 1:
                self._get_text_y = lambda i: self.canvas.height / 2 - self.middle
                return
            spacing = text_height / len(self.lines)
            self._get_text_y = lambda i: i * spacing

    def _update_canvas(self, lines, transition_kwargs):
        self.canvas.delete('all')

        bg = transition_kwargs['bg']
        fg = transition_kwargs['fg']
        decoration_measure = transition_kwargs['decoration_measure']
        underline_width = transition_kwargs['underline_width']
        strike_width = transition_kwargs['strike_width']
        hidden_fg = transition_kwargs['hidden_fg']
        hidden_coords = transition_kwargs['hidden_coords']
        offset = transition_kwargs['offset']
        bdr = transition_kwargs['bdr']
        bd = transition_kwargs['bd']
        bdcolor = transition_kwargs['bdcolor']
        r = transition_kwargs['r']

        self.canvas.create_rectangle(0, 0, self.canvas.width, self.canvas.height, fill=self.parent['bg'], width=0)
        create_rounded_rectangle(self.canvas, 0, 0, self.canvas.width,
                                 self.canvas.height, (bdr, bdr, bdr, bdr), fill=bdcolor)
        create_rounded_rectangle(self.canvas, bd, bd, self.canvas.width - bd,
                                 self.canvas.height - bd, (r, r, r, r), fill=bg)
        self.canvas.bg = bg
        self.canvas.fg = fg
        self.canvas.decoration_measure = decoration_measure
        self.canvas.underline_width = underline_width
        self.canvas.strike_width = strike_width
        self.canvas.hidden_fg = hidden_fg
        self.canvas.hidden_coords = hidden_coords
        self.canvas.offset = offset
        self.canvas.r = r
        self.canvas.bdr = bdr
        self.canvas.bd = bd
        self.canvas.bdcolor = bdcolor

        master_kwargs = self.master_kwargs
        font = master_kwargs['font']
        image = master_kwargs['image']
        hidden_text = master_kwargs['hidden_text']
        hidden_font = master_kwargs['hidden_font']
        ipadx = master_kwargs['ipadx']
        ipady = master_kwargs['ipady']

        if image is not None:
            if self.text is None:
                x = self.canvas.width / 2 - self.image_size[0] / 2
            else:
                x = ipadx + offset / 2
            self.canvas.create_image(x,
                                     self.canvas.height / 2 - self.image_size[1] / 2,
                                     image=image, anchor='nw')

        if hidden_text is not None:
            hx, hy = hidden_coords

            self.canvas.create_text(
                hx, hy, text=hidden_text, fill=hidden_fg, font=hidden_font, anchor='nw', justify='left'
            )

        # Размещаем текст по центру с учетом отступов
        for i, line in enumerate(lines):
            self.canvas.create_text(
                self._get_text_x(i) + offset,
                self._get_text_y(i),
                text=line,
                fill=fg,
                anchor='nw',
                font=font,
                justify='left'
            )
            if underline_width > 0:
                self.canvas.create_line(
                    ipadx + offset + self.image_size[0],
                    ipady + i * self.linespace + self.linespace,
                    ipadx + offset + self.image_size[0] + decoration_measure[i],
                    ipady + i * self.linespace + self.linespace,
                    fill=fg,
                    width=underline_width
                )
            if strike_width > 0:
                self.canvas.create_line(
                    ipadx + offset + self.image_size[0],
                    ipady + i * self.linespace + self.middle,
                    ipadx + offset + self.image_size[0] + decoration_measure[i],
                    ipady + i * self.linespace + self.middle,
                    fill=fg,
                    width=strike_width
                )

    def set_default(self):
        self._update_canvas(self.lines, self.default_kwargs)

    def set_target(self):
        self._update_canvas(self.lines, self.target_kwargs)

    def start_animation(self, transition_kwargs, delay, max_steps, cleartasks=False):
        if hasattr(self.canvas, 'after_id'):
            self.canvas.after_cancel(self.canvas.after_id)
        if cleartasks:
            self.tasks.clear()
        self._animate(transition_kwargs, delay, max_steps, 0)

    @staticmethod
    def _get_next_value(current, target, progress):
        return current + (target - current) * progress

    @staticmethod
    def _get_hex_color(r, g, b):
        return f'#{r // 256:02x}{g // 256:02x}{b // 256:02x}'

    def _animate(self, transition_kwargs, delay, max_steps, current_step):
        if current_step >= max_steps:
            self._update_canvas(self.lines, transition_kwargs)
            if self.tasks:
                task = self.tasks[0]
                indx = task['index']
                delay = task['delay']
                self.canvas.after(delay, self.run_task, indx)
            return

        target_bg = transition_kwargs['bg']
        target_fg = transition_kwargs['fg']
        target_decoration_measure = transition_kwargs['decoration_measure']
        target_underline_width = transition_kwargs['underline_width']
        target_strike_width = transition_kwargs['strike_width']
        target_hidden_fg = transition_kwargs['hidden_fg']
        target_hidden_coords = transition_kwargs['hidden_coords']
        target_offset = transition_kwargs['offset']
        target_r = transition_kwargs['r']
        target_bdr = transition_kwargs['bdr']
        target_bd = transition_kwargs['bd']
        target_bdcolor = transition_kwargs['bdcolor']

        progress = current_step / max_steps

        # Получаем текущие цвета в RGB (0-65535)
        w = self.canvas.toplevel

        br1, bg1, bb1 = w.winfo_rgb(self.canvas.bg)
        br2, bg2, bb2 = w.winfo_rgb(target_bg)

        fr1, fg1, fb1 = w.winfo_rgb(self.canvas.fg)
        fr2, fg2, fb2 = w.winfo_rgb(target_fg)

        hfgr1, hfgg1, hfgb1 = w.winfo_rgb(self.canvas.hidden_fg)
        hfgr2, hfgg2, hfgb2 = w.winfo_rgb(target_hidden_fg)

        bdcolorr1, bdcolorg1, bdcolorb1 = w.winfo_rgb(self.canvas.bdcolor)
        bdcolorr2, bdcolorg2, bdcolorb2 = w.winfo_rgb(target_bdcolor)

        new_br = int(self._get_next_value(br1, br2, progress))
        new_bg = int(self._get_next_value(bg1, bg2, progress))
        new_bb = int(self._get_next_value(bb1, bb2, progress))

        new_fr = int(self._get_next_value(fr1, fr2, progress))
        new_fg = int(self._get_next_value(fg1, fg2, progress))
        new_fb = int(self._get_next_value(fb1, fb2, progress))

        new_decoration_measure = []
        for i in range(len(self.lines) - 1, -1, -1):
            dm = self.canvas.decoration_measure[i]
            if dm == 0 and i > 0:
                new_decoration_measure.insert(0, dm)
                continue
            tdm = target_decoration_measure[i]
            if dm < tdm:
                decoration_exponent = self.animation_kwargs['decoration_exponent_up']
            else:
                decoration_exponent = self.animation_kwargs['decoration_exponent_down']
            new_decoration_measure.insert(0, self._get_next_value(dm, tdm, progress ** decoration_exponent))
        new_underline_width = self._get_next_value(self.canvas.underline_width, target_underline_width, progress)
        new_strike_width = self._get_next_value(self.canvas.strike_width, target_strike_width, progress)

        new_hfgr = int(self._get_next_value(hfgr1, hfgr2, progress))
        new_hfgg = int(self._get_next_value(hfgg1, hfgg2, progress))
        new_hfgb = int(self._get_next_value(hfgb1, hfgb2, progress))

        new_bdcolorr = int(self._get_next_value(bdcolorr1, bdcolorr2, progress))
        new_bdcolorg = int(self._get_next_value(bdcolorg1, bdcolorg2, progress))
        new_bdcolorb = int(self._get_next_value(bdcolorb1, bdcolorb2, progress))

        # Преобразуем в hex (#RRGGBB)
        new_bg_color = self._get_hex_color(new_br, new_bg, new_bb)
        new_fg_color = self._get_hex_color(new_fr, new_fg, new_fb)
        new_hidden_fg_color = self._get_hex_color(new_hfgr, new_hfgg, new_hfgb)
        new_bd_color = self._get_hex_color(new_bdcolorr, new_bdcolorg, new_bdcolorb)

        xc, yc = self.canvas.hidden_coords
        txc, tyc = target_hidden_coords
        if xc < txc:
            x_exponent = self.animation_kwargs['hidden_x_exponent_up']
        else:
            x_exponent = self.animation_kwargs['hidden_x_exponent_down']
        new_hidden_xcoords = self._get_next_value(xc, txc, progress ** x_exponent), self._get_next_value(yc, tyc,
                                                                                                         progress)
        new_offset = self._get_next_value(self.canvas.offset, target_offset, progress)
        new_r = self._get_next_value(self.canvas.r, target_r, progress)
        new_bdr = self._get_next_value(self.canvas.bdr, target_bdr, progress)
        new_bd = self._get_next_value(self.canvas.bd, target_bd, progress)

        new_kwargs = {
            'bg': new_bg_color,
            'fg': new_fg_color,
            'decoration_measure': new_decoration_measure,
            'underline_width': new_underline_width,
            'strike_width': new_strike_width,
            'hidden_fg': new_hidden_fg_color,
            'hidden_coords': new_hidden_xcoords,
            'offset': new_offset,
            'r': new_r,
            'bdr': new_bdr,
            'bd': new_bd,
            'bdcolor': new_bd_color
        }

        self._update_canvas(self.lines, new_kwargs)

        self.canvas.after_id = self.canvas.after(delay, self._animate, transition_kwargs, delay, max_steps,
                                                 current_step + 1)

    def animate_in(self, event=None, cleartasks=False):
        master_kwargs = self.master_kwargs
        state = master_kwargs['state']
        if state == 'normal':
            kwargs = self.target_kwargs
        elif state == 'disabled':
            kwargs = self.disabled_target_kwargs

        animation_kwargs = self.animation_kwargs
        delay = animation_kwargs['delay']
        in_steps = animation_kwargs['in_steps']
        self.start_animation(kwargs, delay, in_steps, cleartasks)

    def animate_out(self, event=None, cleartasks=False):
        master_kwargs = self.master_kwargs
        state = master_kwargs['state']
        if state == 'normal':
            kwargs = self.default_kwargs
        elif state == 'disabled':
            kwargs = self.disabled_default_kwargs

        animation_kwargs = self.animation_kwargs
        delay = animation_kwargs['delay']
        out_steps = animation_kwargs['out_steps']
        self.start_animation(kwargs, delay, out_steps, cleartasks)

    def configure(self, update_function, text=None, default_kwargs=None, target_kwargs=None, master_kwargs=None,
                  animation_kwargs=None, cleartasks=False):
        default_kwargs = default_kwargs or {}
        target_kwargs = target_kwargs or {}
        master_kwargs = master_kwargs or {}
        animation_kwargs = animation_kwargs or {}

        self.default_kwargs = {**self.default_kwargs, **default_kwargs}
        self.target_kwargs = {**self.target_kwargs, **target_kwargs}
        self.master_kwargs = {**self.master_kwargs, **master_kwargs}
        self.animation_kwargs = {**self.animation_kwargs, **animation_kwargs}

        if text is not None:
            self.text = text
        self._update_size()
        match update_function:
            case 'in':
                self.animate_in(cleartasks=cleartasks)
            case 'out':
                self.animate_out(cleartasks=cleartasks)
            case _:
                raise ValueError('Неверное значение update_function. Допустимые значения: "in", "out"')

    def _update_decoration_measure(self):
        if self.default_kwargs['decoration_measure'] is None:
            self.default_kwargs['decoration_measure'] = [0 for _ in self.lines]
        if self.target_kwargs['decoration_measure'] is None:
            decoration_measure = []
            for i in self.lines:
                measure = self.temp_font.measure(i)
                if measure == 0:
                    break
                decoration_measure.append(measure)
            else:
                self.target_kwargs['decoration_measure'] = decoration_measure

    def fix_default_decoration(self):
        self.unfix_decoration()
        self.default_kwargs['decoration_measure'] = self.target_kwargs['decoration_measure']
        self._update_decoration_measure()

    def fix_target_decoration(self):
        self.unfix_decoration()
        self.target_kwargs['decoration_measure'] = self.default_kwargs['decoration_measure']
        self._update_decoration_measure()

    def unfix_decoration(self):
        self.default_kwargs['decoration_measure'] = None
        self.target_kwargs['decoration_measure'] = None
        self._update_decoration_measure()

    def add_task(self, function, delay=0, **kwargs):
        next_index = len(self.tasks)
        self.tasks.append({'index': next_index, 'function': function, 'delay': delay, **kwargs})
        return next_index

    def run_task(self, indx):
        for i in self.tasks:
            if i['index'] == indx:
                self.tasks.remove(i)
                i['function']()
                return True
        return False


class FileAssociation:
    def __init__(self):
        if sys.platform != 'win32':
            raise NotImplementedError(
                'FileAssociation is only supported on Windows. Please use the Windows Registry to set file associations.')

    @staticmethod
    def set_file_association(ext, app_name, app_path, description):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f'Software\\Classes\\{app_name}') as key:
            winreg.SetValue(key, '', winreg.REG_SZ, description)
            with winreg.CreateKey(key, 'shell\\open\\command') as cmd_key:
                winreg.SetValue(cmd_key, '', winreg.REG_SZ, f'"{app_path}" "%1"')

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f'Software\\Classes\\{ext}') as key:
            winreg.SetValue(key, '', winreg.REG_SZ, app_name)

    @staticmethod
    def check_file_association(ext):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, f'Software\\Classes\\{ext}') as key:
                return winreg.QueryValue(key, '')
        except FileNotFoundError:
            return None

    @staticmethod
    def update_explorer():
        os.system('taskkill /f /im explorer.exe')
        os.system('start explorer.exe')


class FontManager:
    @staticmethod
    def install_font(font):
        if FontManager.is_font_installed(font):
            return None

        if not FontManager.run_as_admin():
            return False

        match sys.platform:
            case 'win32':
                # Путь к папке шрифтов Windows
                fonts_dir = os.path.join(os.environ['WINDIR'], 'Fonts')

                # Копируем шрифт в папку Fonts
                shutil.copy(font, fonts_dir)

                # Обновляем реестр (может потребовать запуск от администратора)
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts', 0,
                                        winreg.KEY_SET_VALUE) as key:
                        font_name = os.path.basename(font)
                        winreg.SetValueEx(key, font_name, 0, winreg.REG_SZ, font_name)
                except Exception as e:
                    showinfo('Ошибка', f'Не удалось обновить реестр: {e}')
                    print(f'Не удалось обновить реестр: {e}')
                return True

            case 'linux':
                fonts_dir = os.path.expanduser('/usr/share/fonts/')

                os.makedirs(fonts_dir, exist_ok=True)
                shutil.copy(font, fonts_dir)

                # Обновляем кэш шрифтов
                os.system('fc-cache -fv')
                return True

            case 'darwin':
                fonts_dir = os.path.expanduser('/Library/Fonts/')

                os.makedirs(fonts_dir, exist_ok=True)
                shutil.copy(font, fonts_dir)
                return True

    @staticmethod
    def is_font_installed(font):
        match sys.platform:
            case 'win32':
                return os.path.exists(f'C:/Windows/Fonts/{os.path.basename(font)}')
            case 'linux':
                return os.path.exists(f'/usr/share/fonts/{os.path.basename(font)}')
            case 'darwin':
                return os.path.exists(f'/Library/Fonts/{os.path.basename(font)}')

    @staticmethod
    def run_as_admin():
        if FontManager.is_admin():
            return True  # Уже запущено от админа

        match sys.platform:
            case 'win32':
                script = os.path.abspath(sys.argv[0])
                params = ' '.join([f'"{x}"' for x in sys.argv[1:]])
                working_dir = os.path.dirname(script)

                # Проверяем, скомпилирован ли код с помощью Nuitka
                # Nuitka устанавливает атрибут __compiled__ при компиляции
                if hasattr(sys, 'frozen') or hasattr(sys, '_MEIPASS') or '__compiled__' in globals():
                    # Для скомпилированного EXE
                    ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", script, params, working_dir, 1
                    )
                else:
                    # Для интерпретатора Python
                    ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", sys.executable, f'"{script}" {params}', working_dir, 0
                    )
                return False

            case 'linux':
                try:
                    os.execvp('gksudo', ['gksudo', '--', sys.executable] + sys.argv)
                except FileNotFoundError:
                    print('gksudo не найден. Попробуем sudo...')
                    os.execvp('sudo', ['sudo', sys.executable] + sys.argv)

            case 'darwin':
                os.execvp('sudo', ['sudo', sys.executable] + sys.argv)

    @staticmethod
    def is_admin():
        if sys.platform == 'win32':
            try:
                return ctypes.windll.shell32.IsUserAnAdmin()
            except:
                return False

        if sys.platform in ('linux', 'darwin'):
            return os.getuid() == 0


class WindowManager:
    @staticmethod
    def CreateWindow(master=None, title=None, bg=None, resizable=(False, False), state='normal', icon=True,
                     switch_fullscreen=True, switch_topmost=True, attrs=None):
        win = tk.Tk() if master is None else tk.Toplevel(master)
        win.title(title)
        win.resizable(*resizable)
        win['bg'] = bg
        win.state(state)
        if icon and os.path.exists('Scheduler.ico'):
            win.iconbitmap('Scheduler.ico')
        if attrs is None:
            attrs = {}
        for key, value in attrs.items():
            win.attributes(key, value)
        if switch_fullscreen:
            win.bind('<F10>', lambda event: WindowManager.SwitchAttribute(win, '-fullscreen'))
        if switch_topmost:
            win.bind('<F11>', lambda event: WindowManager.SwitchAttribute(win, '-topmost'))
        return win

    @staticmethod
    def SwitchAttribute(window, attribute, value=None):
        if value is None:
            window.attributes(attribute, not window.attributes(attribute))
        else:
            window.attributes(attribute, value)

    @staticmethod
    def on_mousewheel(event, canvas):
        # Проверяем, нужна ли прокрутка
        if canvas.yview() != (0.0, 1.0):  # Если скролл не в крайних положениях
            canvas.yview_scroll(-1 * (event.delta // 120), 'units')  # Прокручиваем
        else:
            return 'break'  # Блокируем прокрутку

    @staticmethod
    def OnTopWindow(win: tk.Tk | tk.Toplevel) -> None:
        win.attributes('-topmost', True)
        win.attributes('-topmost', False)

    @staticmethod
    def PlaceWindow(w, parent=None, ForciblyPlace=False):
        w.wm_withdraw()  # Remain invisible while we figure out the geometry
        w.update_idletasks()  # Actualize geometry information

        minwidth = w.winfo_reqwidth()
        minheight = w.winfo_reqheight()
        maxwidth = w.winfo_vrootwidth()
        maxheight = w.winfo_vrootheight()
        if parent is not None and (parent.winfo_ismapped() or ForciblyPlace):
            x = parent.winfo_rootx() + (parent.winfo_width() - minwidth) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - minheight) // 2
            vrootx = w.winfo_vrootx()
            vrooty = w.winfo_vrooty()
            x = min(x, vrootx + maxwidth - minwidth)
            x = max(x, vrootx)
            y = min(y, vrooty + maxheight - minheight)
            y = max(y, vrooty)
            if w._windowingsystem == 'aqua':
                # Avoid the native menu bar which sits on top of everything.
                y = max(y, 22)
        else:
            x = (w.winfo_screenwidth() - minwidth) // 2
            y = (w.winfo_screenheight() - minheight) // 2

        w.wm_maxsize(maxwidth, maxheight)
        w.wm_geometry('+%d+%d' % (x, y))
        w.wm_deiconify()  # Become visible at the desired location
        if parent:
            parent.withdraw()
        w.deiconify()
        WindowManager.OnTopWindow(w)

    @staticmethod
    def SetToCenter(win) -> None:
        """
        SetToCenter(self, win: tk.Tk) -> None
        Выравнивание окна по центру экрана
        """
        win.deiconify()
        win.update_idletasks()  # Приостановка кода для выравнивания
        width = win.winfo_width()  # Получение ширины окна
        frm_width = win.winfo_rootx() - win.winfo_x()  # Получение координаты x окна
        win_width = width + 2 * frm_width  # Вычисление ширины окна
        height = win.winfo_height()  # Получение высоты окна
        titlebar_height = win.winfo_rooty() - win.winfo_y()  # Получение высоты заголовка окна
        win_height = height + titlebar_height + frm_width  # Вычисление высоты окна
        x = win.winfo_screenwidth() // 2 - win_width // 2  # Получение координаты x для окна
        y = win.winfo_screenheight() // 2 - win_height // 2 - 30  # Получение координаты y для окна
        win.geometry('+{}+{}'.format(x, y))  # Применение расположения окна
        win.focus_force()  # Фокусировка на окне

    @staticmethod
    def FixWindowSize(win, width=None, height=None):
        win.update_idletasks()
        if width is None:
            width = win.winfo_width()
        if height is None:
            height = win.winfo_height()
        win.geometry(f'{width}x{height}')


def glob(*args, **kwargs):
    """
    I wrote my own glob() function using glob.glob() because I'm dumb
    """
    return [i.replace('\\', '/') for i in shitty_glob(*args, **kwargs)]


"""
def CreateButton(master=None, text=None, image=None, command=None, row=None, column=None, animation_kwargs=None, **options) -> tk.Button:
    animation_kwargs = animation_kwargs or {}
    options = options['options'] if 'options' in options else options
    if 'enterbackground' in options:
        raise ValueError('enterbackground is deprecated. Use activebackground instead.')
    if 'enterforeground' in options:
        raise ValueError('enterforeground is deprecated. Use activeforeground instead.')

    font = options['font'] if 'font' in options else 'helvetica 14'
    foreground = options['fg'] if 'fg' in options else 'white'
    background = options['bg'] if 'bg' in options else 'black'
    activeforeground = options['activeforeground'] if 'activeforeground' in options else background
    activebackground = options['activebackground'] if 'activebackground' in options else foreground
    borderwidth = options['bd'] if 'bd' in options else 2
    width = options['width'] if 'width' in options else None
    height = options['height'] if 'height' in options else None
    relief = options['relief'] if 'relief' in options else None
    command = None if 'state' in options and options['state'] == 'disabled' else command

    button = tk.Button(master, text=text, command=command, font=font, image=image,
                       fg=foreground, bg=background, activeforeground=activeforeground,
                       activebackground=activebackground, bd=borderwidth, width=width, height=height,
                       relief=relief, disabledforeground=foreground)

    highlight = options['highlight'] if 'highlight' in options else True
    if highlight:
        startfade = options['startfade'] if 'startfade' in options else False
        FadeEffect(button, activebackground, activeforeground, startfade=startfade, **animation_kwargs)

    if 'bind' in options:
        for bind, command in options['bind'].items():
            button.bind(bind, command)

    rowspan = options['rowspan'] if 'rowspan' in options else 1
    columnspan = options['columnspan'] if 'columnspan' in options else 1
    padx = options['padx'] if 'padx' in options else 5
    pady = options['pady'] if 'pady' in options else 5
    sticky = options['sticky'] if'sticky' in options else 'nesw'

    if None not in (row, column):
        button.grid(row=row, column=column, rowspan=rowspan, columnspan=columnspan, padx=padx, pady=pady, sticky=sticky)
    return button
"""


def CreateButton(parent, text=None, command=None, event=False,
                 default_kwargs=None, target_kwargs=None, master_kwargs=None, animation_kwargs=None):
    if command is None:
        bind = None
    else:
        bind = [('<Button-1>', command, event)]
    btn = CanvasAnimation(
        parent, text, bind,
        default_kwargs=default_kwargs,
        target_kwargs=target_kwargs,
        master_kwargs=master_kwargs,
        animation_kwargs=animation_kwargs,
    )
    return btn


def declination(number, words=('секунду', 'секунды', 'секунд')):
    """Просклоняет и возвращает слово"""
    units = number % 10
    tens = number % 100 - units
    if tens == 10 or units >= 5 or units == 0:
        return words[2]
    elif units > 1:
        return words[1]
    return words[0]


def hex_to_rgb(hex_color):
    """
    Преобразует шестнадцатеричный код цвета в формат RGB.

    Args:
        hex_color: Строка, представляющая шестнадцатеричный код цвета (например, "#FF0000").

    Returns:
        Кортеж из трех целых чисел, представляющих значения RGB (например, (255, 0, 0)).
        Возвращает None, если входная строка не является допустимым шестнадцатеричным кодом.
    """
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        return None
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return r, g, b
    except ValueError:
        return None


def change_image_color(image_file, color_rgb):
    img = Image.open(image_file).convert('RGBA')

    pixdata = img.load()

    for y in range(img.size[1]):
        for x in range(img.size[0]):
            alpha = pixdata[x, y][3]
            if alpha:
                pixdata[x, y] = (*color_rgb, alpha)

    img.save(image_file)


def PlaceText(text, width, fontname=None, font=None):
    if fontname is not None:
        temp_font = tk.font.Font(font=fontname)
    elif font is not None:
        temp_font = font
    else:
        raise ValueError('Не указан ни параметр fontname, ни параметр font.')
    # Разбиваем текст на строки с переносом
    words = text.split()
    lines = []
    current_line = []
    current_width = 0

    for word in words:
        word_width = temp_font.measure(word + ' ')
        if current_width + word_width <= width or not current_line:
            current_line.append(word)
            current_width += word_width
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
            current_width = word_width

    if current_line:
        lines.append(' '.join(current_line))
    return '\n'.join(lines)


def get_file_type_description(file_path):
    basename = os.path.basename(file_path)
    if '.' in basename:
        elements = basename.split('.')
        ext = elements[-1].upper()
        return f'Файл "{ext}"'
    else:
        return 'Папка с файлами'


def create_animation_from_font(font_path, output_gif='animation.gif',
                               fill=(0, 0, 0, 255), background=(255, 255, 255, 255),
                               font_size=100, duration=30,
                               start_code=0xE052, end_code=0xE0CB):
    """Полностью автоматическое центрирование и кадрирование"""

    font = ImageFont.truetype(font_path, font_size)
    bgr = []
    for i in range(3):
        bgr.append(background[i])
    bgr = tuple(bgr)

    # Этап 1: Рендерим все символы и находим общий bounding box
    all_images = []
    temp_size = (128, 128)

    for char_code in range(start_code, end_code + 1):
        try:
            char = chr(char_code)
            image = Image.new('RGBA', temp_size, (255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.text((200, 200), char, font=font, fill=(0, 0, 0, 255), anchor="mm")
            all_images.append(image)
        except:
            continue

    if not all_images:
        print("Не удалось создать ни одного кадра")
        return

    # Находим объединенный bounding box
    min_left, min_top, max_right, max_bottom = temp_size[0], temp_size[1], 0, 0

    for img in all_images:
        bbox = img.getbbox()
        if bbox:
            min_left = min(min_left, bbox[0])
            min_top = min(min_top, bbox[1])
            max_right = max(max_right, bbox[2])
            max_bottom = max(max_bottom, bbox[3])

    # Добавляем отступы
    padding = 15
    crop_box = (min_left - padding, min_top - padding,
                max_right + padding, max_bottom + padding)

    # Размер итогового кадра
    final_width = crop_box[2] - crop_box[0]
    final_height = crop_box[3] - crop_box[1]

    print(f"Автоматически определенный размер: {final_width}x{final_height}")

    # Этап 2: Создаем финальные кадры
    frames = []

    for char_code in range(start_code, end_code + 1):
        try:
            char = chr(char_code)

            # Создаем изображение достаточного размера
            temp_image = Image.new('RGBA', (final_width + 100, final_height + 100), background)
            draw = ImageDraw.Draw(temp_image)

            # Центр временного изображения
            center_x, center_y = temp_image.size[0] // 2, temp_image.size[1] // 2

            # Рисуем символ по центру
            draw.text((center_x, center_y), char, font=font, fill=fill, anchor="mm")

            # Кадрируем до финального размера
            left = center_x - final_width // 2
            top = center_y - final_height // 2
            right = center_x + final_width // 2
            bottom = center_y + final_height // 2

            cropped_image = temp_image.crop((left, top, right, bottom))

            # Конвертируем в RGB
            rgb_image = Image.new('RGB', cropped_image.size, bgr)
            rgb_image.paste(cropped_image, mask=cropped_image.split()[3])

            frames.append(rgb_image)

        except Exception as e:
            print(f"Пропуск символа U+{char_code:04X}: {e}")

    imageio.mimsave(output_gif, frames, duration=duration, loop=0)
    print(f"Автоматически центрированная анимация сохранена: {output_gif}")


def create_rounded_rectangle(canvas, x1, y1, x2, y2, radius, **kwargs):
    radius1, radius2, radius3, radius4 = radius
    points = [x1 + radius1, y1,
              x2 - radius2, y1,
              x2, y1,
              x2, y1 + radius2,
              x2, y2 - radius3,
              x2, y2,
              x2 - radius3, y2,
              x1 + radius4, y2,
              x1, y2,
              x1, y2 - radius4,
              x1, y1 + radius1,
              x1, y1]
    return canvas.create_polygon(points, **kwargs, smooth=True)


def askstring(title=None, prompt=None, master=None, initialvalue=None, yesno=None, showinfo=None, yesnocancel=None,
              rootWin=None, destroyWin=None, fg=None, bg=None, font=None, animation_kwargs=None,
              **options) -> str | bool | None:
    animation_kwargs = animation_kwargs or {}
    options = options['options'] if 'options' in options else options

    if fg is None:
        fg = 'white'
    if bg is None:
        bg = 'black'
    if font is None:
        font = 'Arial 14'

    def _yes(event=None) -> None:
        root.quit()
        if destroyWin:
            root.destroy()

    def _no(event=None) -> None:
        _yes()
        result.no = True

    def _cancel(event=None) -> None:
        _yes()
        result.cancel = True

    if rootWin:
        root = rootWin
        root.title(title)
    else:
        root = WindowManager.CreateWindow(master=master, title=title, bg=bg, switch_fullscreen=False)
    root.attributes('-topmost', True)

    if destroyWin is None:
        destroyWin = True
    isaskstring = all(tuple(i is None for i in (yesno, showinfo, yesnocancel)))

    justify = options['justify'] if 'justify' in options else 'center'
    columnspan = 3 if yesnocancel else 2 if showinfo is None else 1

    if title and prompt:
        title_size = len(title)
        prompt_size = len(prompt)
        difference = title_size - prompt_size
        if showinfo:
            difference = 50 - abs(difference)
        num = difference if difference > 0 else 20
        space = ' ' * ((num - prompt_size + title_size) // 2)
        prompt = space + prompt + space

    tk.Label(root, text=prompt, justify=justify, font=font, fg=fg, bg=bg).grid(row=0, column=0, columnspan=columnspan,
                                                                               padx=5, pady=5, sticky='nesw')
    result = tk.StringVar(root, value=initialvalue)
    result.no = False
    result.cancel = False
    if isaskstring:
        entry = tk.Entry(root, textvariable=result, font=font, fg=fg, bg=bg, insertbackground=fg)
        entry.grid(row=1, column=0, columnspan=columnspan, padx=5, pady=5, sticky='nesw')

    root.update_idletasks()
    width = root.winfo_width()
    if showinfo:
        numbtn = 1
    elif yesnocancel:
        numbtn = 3
    else:
        numbtn = 2
    btn_width = width // numbtn

    text = options['yes_text'] if 'yes_text' in options else 'Продолжить'
    CreateButton(
        root, text, _yes,
        default_kwargs={'bg': bg, 'fg': fg, 'r': 8, 'bd': 1, 'bdr': 10, 'bdcolor': fg},
        target_kwargs={'bg': fg, 'fg': bg, 'offset': 0, 'bd': 1, 'bdcolor': fg},
        master_kwargs={'font': font, 'width': btn_width, 'text_align': 'center',
                       'place': {'method': 'grid', 'row': 2, 'column': 0, 'sticky': 'nesw'}},
        animation_kwargs=animation_kwargs,
    )
    if showinfo is None:
        text = options['no_text'] if 'no_text' in options else 'Отмена'
        command = _cancel if yesnocancel is None else _no
        CreateButton(
            root, text, command,
            default_kwargs={'bg': bg, 'fg': fg, 'r': 8, 'bd': 1, 'bdr': 10, 'bdcolor': fg},
            target_kwargs={'bg': fg, 'fg': bg, 'offset': 0, 'bd': 1, 'bdcolor': fg},
            master_kwargs={'font': font, 'width': btn_width, 'text_align': 'center',
                           'place': {'method': 'grid', 'row': 2, 'column': 1, 'sticky': 'nesw'}},
            animation_kwargs=animation_kwargs,
        )
    if yesnocancel:
        text = options['cancel_text'] if 'cancel_text' in options else 'Отмена'
        CreateButton(
            root, text, _cancel,
            default_kwargs={'bg': bg, 'fg': fg, 'r': 8, 'bd': 1, 'bdr': 10, 'bdcolor': fg},
            target_kwargs={'bg': fg, 'fg': bg, 'offset': 0, 'bd': 1, 'bdcolor': fg},
            master_kwargs={'font': font, 'width': btn_width, 'text_align': 'center',
                           'place': {'method': 'grid', 'row': 2, 'column': 2, 'sticky': 'nesw'}},
            animation_kwargs=animation_kwargs,
        )

    root.bind('<space>', _yes)
    root.bind('<Return>', _yes)
    root.bind('<Escape>', _cancel)
    root.protocol('WM_DELETE_WINDOW', _cancel)

    WindowManager.PlaceWindow(root, master, ForciblyPlace=True)

    if isaskstring:
        entry.focus()
        entry.select_range(0, 'end')
        entry.icursor('end')

    root.mainloop()

    yes_deiconify = options['yes_deiconify'] if 'yes_deiconify' in options else False
    no_deiconify = options['no_deiconify'] if 'no_deiconify' in options else False
    cancel_deiconify = options['cancel_deiconify'] if 'cancel_deiconify' in options else not showinfo
    if master:
        if (result.no and no_deiconify) or (result.cancel and cancel_deiconify) or yes_deiconify:
            master.deiconify()
    if result.no:
        return False
    if result.cancel:
        return None
    if isaskstring:
        return result.get()
    return True


def askinteger(title=None, prompt=None, master=None, initialvalue=None, rootWin=None, destroyWin=None, fg=None, bg=None,
               font=None, animation_kwargs=None, **options) -> str | None:
    result = askstring(title, prompt, master, initialvalue, rootWin=rootWin, destroyWin=destroyWin, fg=fg, bg=bg,
                       font=font, animation_kwargs=animation_kwargs, options=options)
    if result is None:
        return None
    result = ''.join(tuple(i for i in result if i.isdigit()))
    if result == '':
        return None
    return eval(result)


def askyesno(title=None, prompt=None, master=None, rootWin=None, destroyWin=None, fg=None, bg=None, font=None,
             animation_kwargs=None, **options) -> bool:
    return askstring(title, prompt, master, yesno=True, rootWin=rootWin, destroyWin=destroyWin, fg=fg, bg=bg, font=font,
                     animation_kwargs=animation_kwargs, options=options)


def showinfo(title=None, prompt=None, master=None, rootWin=None, destroyWin=None, fg=None, bg=None, font=None,
             animation_kwargs=None, **options) -> None:
    return askstring(title, prompt, master, showinfo=True, rootWin=rootWin, destroyWin=destroyWin, deiconify=True,
                     fg=fg, bg=bg, font=font, animation_kwargs=animation_kwargs, options=options)


def askyesnocancel(title=None, prompt=None, master=None, rootWin=None, destroyWin=None, fg=None, bg=None, font=None,
                   animation_kwargs=None, **options) -> bool:
    return askstring(title, prompt, master, yesnocancel=True, rootWin=rootWin, destroyWin=destroyWin, fg=fg, bg=bg,
                     font=font, animation_kwargs=animation_kwargs, options=options)


def mainloop():
    while True:
        scheduler = Scheduler()
        if scheduler.RESTART:
            continue
        break


def main():
    if len(set(sys.argv)) == 1:
        mainloop()
    else:
        def create(folder, obj, filename, ext='.txt'):
            target = f'{folder}/{filename}{ext}'
            if os.path.exists(target):
                errors.append(('Файл уже существует', target))
            else:
                try:
                    shutil.copy(obj, target)
                    successes.append(('Файл создан', target))
                except Exception as e:
                    errors.append((f'Ошибка при создании файла: {e}', target))

        def replace(folder, obj, filename, ext='.txt'):
            target = f'{folder}/{filename}{ext}'
            if os.path.exists(target):
                try:
                    os.remove(target)
                except Exception as e:
                    errors.append((f'Ошибка при замене файла: {e}', target))
                    return
                replaced = True
            else:
                replaced = False
            try:
                shutil.copy(obj, target)
            except Exception as e:
                errors.append((f'Ошибка при замене файла: {e}', target))
                return
            if replaced:
                successes.append(('Файл заменён', target))
            else:
                successes.append(('Файл создан', target))

        objects = sys.argv[1:]
        errors = []
        successes = []

        for obj in objects:
            if not os.path.exists(obj):
                continue
            basename = os.path.basename(obj)
            filename, ext = os.path.splitext(basename)

            match ext:
                case '.scheduler-data':
                    if os.path.exists(f'Scheduler_Data/Temp/{filename}.zip'):
                        os.remove(f'Scheduler_Data/Temp/{filename}.zip')
                    shutil.copy(obj, f'Scheduler_Data/Temp/{filename}.zip')
                    if os.path.exists(f'Scheduler_Data/Temp/{filename}'):
                        shutil.rmtree(f'Scheduler_Data/Temp/{filename}')
                    try:
                        with ZipFile(f'Scheduler_Data/Temp/{filename}.zip', 'r', metadata_encoding='utf-8') as zip_file:
                            zip_file.extractall(f'Scheduler_Data/Temp/{filename}')
                    except BadZipFile:
                        errors.append(('Файл установки компонентнов Scheduler повреждён', obj))
                        continue

                    for file in glob(f'Scheduler_Data/Temp/{filename}/*'):
                        subbasename = os.path.basename(file)
                        subfilename, subext = os.path.splitext(subbasename)

                        match subext:
                            case '.srsched':
                                replace('Scheduler_Data/Schedules', file, subfilename)
                            case '.ssched':
                                create('Scheduler_Data/Schedules', file, subfilename)

                            case '.srtheme':
                                replace('Scheduler_Data/Themes', file, subfilename)
                            case '.stheme':
                                create('Scheduler_Data/Themes', file, subfilename)

                            case '.srfontdata':
                                if not os.path.exists(f'Scheduler_Data/Fonts/{subfilename}'):
                                    os.mkdir(f'Scheduler_Data/Fonts/{subfilename}')
                                data = eval(open('requirements.ini', 'r', encoding='utf-8').read())
                                if f'Scheduler_Data/Fonts/{subfilename}' not in data['main']:
                                    data['main'][f'Scheduler_Data/Fonts/{subfilename}'] = []
                                    open('requirements.ini', 'w', encoding='utf-8').write(str(data))
                                replace(f'Scheduler_Data/Fonts/{subfilename}', file, subfilename, '.dat')
                            case '.sfontdata':
                                if not os.path.exists(f'Scheduler_Data/Fonts/{subfilename}'):
                                    os.mkdir(f'Scheduler_Data/Fonts/{subfilename}')
                                data = eval(open('requirements.ini', 'r', encoding='utf-8').read())
                                if f'Scheduler_Data/Fonts/{subfilename}' not in data['main']:
                                    data['main'][f'Scheduler_Data/Fonts/{subfilename}'] = []
                                    open('requirements.ini', 'w', encoding='utf-8').write(str(data))
                                create(f'Scheduler_Data/Fonts/{subfilename}', file, subfilename, '.dat')

                            case '.srfont':
                                if not os.path.exists(f'Scheduler_Data/Fonts/{subfilename}'):
                                    os.mkdir(f'Scheduler_Data/Fonts/{subfilename}')
                                replace(f'Scheduler_Data/Fonts/{subfilename}', file, subfilename, '.ttf')
                            case '.sfont':
                                if not os.path.exists(f'Scheduler_Data/Fonts/{subfilename}'):
                                    os.mkdir(f'Scheduler_Data/Fonts/{subfilename}')
                                create(f'Scheduler_Data/Fonts/{subfilename}', file, subfilename, '.ttf')

                            case '.srfontsize':
                                replace('Scheduler_Data/FontSizes', file, subfilename)
                            case '.sfontsize':
                                create('Scheduler_Data/FontSizes', file, subfilename)

                            case '.sranimgif':
                                replace('Scheduler_Data/Animations/GIFs', file, subfilename, '.gif')
                            case '.sanimgif':
                                create('Scheduler_Data/Animations/GIFs', file, subfilename, '.gif')

                            case '.sranimpreset':
                                replace('Scheduler_Data/Animations/presets', file, subfilename)
                            case '.sanimpreset':
                                create('Scheduler_Data/Animations/presets', file, subfilename)

                            case _:
                                errors.append(('Неподдерживаемый формат файла', subbasename, 'внутри', obj))

                    os.remove(f'Scheduler_Data/Temp/{filename}.zip')
                    shutil.rmtree(f'Scheduler_Data/Temp/{filename}')

                case _:
                    errors.append(('Неподдерживаемый формат файла', obj))

        text = 'Обработка файлов завершена.\n'
        if errors:
            text += '\nОшибки:\n'
            for error in errors:
                text += f'{error[0]}: {error[1]}\n'
        if successes:
            text += '\nУспешно:\n'
            for success in successes:
                text += f'{success[0]}: {success[1]}\n'
        showinfo('Scheduler - Обработка файлов', text)


if __name__ == '__main__':
    main()
