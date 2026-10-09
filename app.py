"""Wire Judge v1.1 — local native-VTR approach viewer."""
from pathlib import Path
from collections import defaultdict
from dataclasses import asdict
import json, os, queue, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from toolbar import GraphToolbar,DeferredFigureCanvasTkAgg
from reader import read_motion
from engine import Settings,auto_bolter,analyze,last_attempts,player_label,clock,glide_origin_msl_ft,glide_start_nm,target_intercept_nm,black_box_data,BLACK_BOX_METRICS
from plots import make_figure,draw,BG,PANEL,TEXT,MUTED,GREEN,START_END_COLOR,ATTEMPT_COLORS,MAX_COMPARE_ATTEMPTS,ApproachCursor
from annotations import Annotations,WIRE_OPTIONS,replay_digest
from attempt_edits import AttemptEdits
from app_animations import ApplicationAnimations
from editor import AttemptEditorPage
from scoring import score_attempt,best_by_player,is_best,maximum,approach_maximum
from score_window import ScoreWindow
from replay_map import ReplayMapPage

SETTINGS_PATH=Path.home()/'.wire_judge'/'settings.json'
ANNOTATIONS_DIR=Path.home()/'.wire_judge'/'annotations'
AGREEMENT_PATH=Path.home()/'.wire_judge'/'agreement.json'
ASSETS_DIR=Path(__file__).resolve().parent/'assets'
APP_VERSION='1.1'
STARTUP_TERMS=(
    'All scores and calculations are subject to change. By clicking “I Agree,” you acknowledge that STRAYDOG and any applications created by STRAYDOG are not responsible for emotional distress, bruised egos, damaged flight controls, or heated Discord arguments resulting from your questionable approach.',
    'Software bugs and calculation errors may occur. However, their existence does not automatically explain your bolter.',
    'By continuing, you accept these terms and the possibility that the problem was, in fact, not the plane… but the pilot.'
)

class WireJudge(tk.Tk):
    def __init__(self):
        super().__init__();self.withdraw();self.title(f'Wire Judge V{APP_VERSION} · BY: STRAYDOG0626');self.geometry('1380x900');self.minsize(1050,760);self.configure(bg=BG)
        self.app_icon=tk.PhotoImage(file=str(ASSETS_DIR/'app_icon.png'))
        self.header_logo=tk.PhotoImage(file=str(ASSETS_DIR/'header_logo.png'))
        self.iconphoto(True,self.app_icon)
        self.settings=Settings.load(SETTINGS_PATH);self.tracks=[];self.attempts=[];self.selected=None;self.carrier=None;self.filename=None;self.busy=False;self.messages=queue.Queue()
        self.annotations=None;self.comparison_ids=[]
        self.edits=None;self.auto_attempts=[];self.settings_path=SETTINGS_PATH;self.row_players={}
        self.scores={};self.best_scores={};self.score_window=None
        style=ttk.Style(self);style.theme_use('clam')
        style.configure('.',background=BG,foreground=TEXT,font=('Helvetica',11))
        style.configure('TFrame',background=BG);style.configure('TLabel',background=BG,foreground=TEXT)
        style.configure('TNotebook',background=BG,borderwidth=0)
        style.configure('TNotebook.Tab',background='#24374d',foreground=TEXT,padding=(10,4),font=('Helvetica',10))
        style.map('TNotebook.Tab',background=[('selected','#355372'),('active','#355372')],foreground=[('selected',TEXT)],padding=[('selected',(18,10)),('!selected',(10,4))],font=[('selected',('Helvetica',12,'bold')),('!selected',('Helvetica',10))],expand=[('selected',(2,2,2,0)),('!selected',(0,0,0,0))])
        style.configure('TButton',background='#24374d',foreground=TEXT,padding=(12,8),borderwidth=0)
        style.map('TButton',background=[('active','#355372')])
        for name,base,active in (('NeedsInput','#963f48','#b44b56'),('Selected','#27694e','#328563')):
            style.configure(name+'.TButton',background=base,foreground='#ffffff')
            style.map(name+'.TButton',background=[('active',active),('disabled',base)],foreground=[('disabled','#c9c9c9')])
        style.configure('TCheckbutton',background=BG,foreground=TEXT)
        style.configure('Treeview',background='#182436',fieldbackground='#182436',foreground=TEXT,rowheight=30,borderwidth=0)
        style.map('Treeview',background=[('selected','#294b70')],foreground=[])
        style.configure('TEntry',fieldbackground='#24374d',foreground=TEXT,insertcolor=TEXT)
        style.configure('TCombobox',fieldbackground='#24374d',foreground=TEXT,arrowcolor=TEXT)
        style.map('TCombobox',fieldbackground=[('readonly','#24374d'),('disabled','#182436')],foreground=[('readonly',TEXT),('disabled',MUTED)])
        top=ttk.Frame(self,padding=(16,12));top.pack(fill='x')
        self.open_btn=ttk.Button(top,text='Select Replay',command=self.open_file);self.open_btn.pack(side='left',padx=10)
        self.carrier_btn=ttk.Button(top,text='Select Carrier',command=self.choose_carrier,state='disabled');self.carrier_btn.pack(side='left')
        ttk.Label(top,text='Recovery:').pack(side='left',padx=(20,8))
        self.case_value=tk.StringVar(value=f'Case {self.settings.recovery_case}')
        style.layout('Recovery.TRadiobutton',style.layout('TButton'))
        style.configure('Recovery.TRadiobutton',background='#24374d',foreground=TEXT,padding=(12,8),borderwidth=0)
        style.map('Recovery.TRadiobutton',background=[('selected','#27694e'),('active','#355372')])
        self.case_buttons=[]
        for case in (1,3):
            button=ttk.Radiobutton(top,text=f'Case {case}',value=f'Case {case}',variable=self.case_value,
                                  command=self.change_case,style='Recovery.TRadiobutton')
            button.pack(side='left',padx=(0,5));self.case_buttons.append(button)
        self.points_value=tk.BooleanVar(value=self.settings.show_data_points)
        
        self.update_input_buttons()
        brand=ttk.Frame(top);brand.pack(side='right')
        self.logo_label=ttk.Label(brand,image=self.header_logo,cursor='hand2')
        self.logo_label.pack(side='left',padx=(0,8))
        self.logo_label.bind('<Button-1>',lambda event:self.animations.trigger_ufo(from_logo=True))
        ttk.Label(brand,text=f'WIRE JUDGE V{APP_VERSION}',font=('Helvetica',16,'bold')).pack(side='left')
        self.content=ttk.Frame(self);self.content.pack(fill='both',expand=True,padx=16,pady=(0,8))
        self.carrier_selection=None
        self.pages=ttk.Notebook(self.content);self.pages.pack(fill='both',expand=True)
        self.approach_page=ttk.Frame(self.pages);self.settings_page=ttk.Frame(self.pages)
        self.pages.add(self.approach_page,text='Approach Viewer')
        self.score_window=ScoreWindow(self,self.pages);self.pages.add(self.score_window,text='Scoreboard')
        self.editor_page=AttemptEditorPage(self,self.pages);self.pages.add(self.editor_page,text='Attempt Editor')
        self.replay_map=ReplayMapPage(self,self.pages);self.pages.insert(self.score_window,self.replay_map,text='Replay Map')
        self.pages.add(self.settings_page,text='Settings')
        body=ttk.Panedwindow(self.approach_page,orient='horizontal');body.pack(fill='both',expand=True)
        left=ttk.Frame(body,padding=(0,4,12,4));right=ttk.Frame(body);body.add(left,weight=1);body.add(right,weight=4)
        ttk.Label(left,text='PLAYERS & APPROACHES',font=('Helvetica',11,'bold')).pack(anchor='w',pady=(0,8))
        self.attempt_filter=tk.StringVar(value='All')
        filterbar=ttk.Frame(left);filterbar.pack(fill='x',pady=(0,10))
        ttk.Label(filterbar,text='Show:').pack(side='left',padx=(0,8))
        self.attempt_filter_select=ttk.Combobox(filterbar,textvariable=self.attempt_filter,values=('All','Last attempt','Best attempt'),state='readonly',width=16)
        self.attempt_filter_select.pack(side='left');self.attempt_filter_select.bind('<<ComboboxSelected>>',lambda *_:self.populate())
        self.player_search=tk.StringVar();search=ttk.Entry(left,textvariable=self.player_search);search.pack(fill='x');self.player_search.trace_add('write',lambda *_:self.populate())
        ttk.Label(left,text='Search player or aircraft',foreground=MUTED,font=('Helvetica',9)).pack(anchor='w',pady=(3,10))
        treeframe=ttk.Frame(left);treeframe.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(treeframe,show='tree',selectmode='none');self.tree.column('#0',width=350,minwidth=250);self.tree.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(treeframe,orient='vertical',command=self.tree.yview);scroll.pack(side='right',fill='y');self.tree.configure(yscrollcommand=scroll.set);self.tree.bind('<<TreeviewSelect>>',self.select_attempt)
        self.tree.bind('<Double-1>',self.open_player_editor)
        self.tree.bind('<Button-1>',self.toggle_comparison_row)
        self.tree.bind('<ButtonRelease-1>',lambda _: 'break')
        self.tree.bind('<Shift-Button-1>',self.toggle_comparison_row)
        self.compare_icons=[]
        for color,_ in ATTEMPT_COLORS:
            icon=tk.PhotoImage(width=16,height=16)
            for y in range(16):
                for x in range(16):
                    if (x-7.5)**2+(y-7.5)**2<=25:icon.put(color,(x,y))
            self.compare_icons.append(icon)
        self.count_text=tk.StringVar(value='No replay loaded')
        wirebar=ttk.Frame(left,padding=(0,8,0,4));wirebar.pack(side='bottom',fill='x',before=treeframe)
        ttk.Label(wirebar,text='Wire Caught:').pack(side='left')
        self.wire_value=tk.StringVar();self.wire_select=ttk.Combobox(wirebar,textvariable=self.wire_value,values=WIRE_OPTIONS,width=9,state='disabled');self.wire_select.pack(side='left',padx=8);self.wire_select.bind('<<ComboboxSelected>>',self.set_wire)
        self.fig=make_figure();self.canvas=DeferredFigureCanvasTkAgg(self.fig,master=right);self.canvas.get_tk_widget().pack(fill='both',expand=True)
        graphbar=ttk.Frame(right);graphbar.pack(side='bottom',fill='x',before=self.canvas.get_tk_widget())
        self.toolbar=GraphToolbar(self.canvas,graphbar)
        self.graph_cursor=ApproachCursor(self.canvas,self.toolbar,lambda:self.selected,self.jump_to_replay)
        self.data_points_btn=ttk.Button(self.toolbar,text='Data Points',command=lambda:(self.points_value.set(not self.points_value.get()),self.toggle_points()))
        self.data_points_btn.pack(side='left',padx=(0,6))
        def update_data_points_style(*_):self.data_points_btn.configure(style='Selected.TButton' if self.points_value.get() else 'TButton')
        self.points_value.trace_add('write',update_data_points_style);update_data_points_style()
        graph_toggles=ttk.Frame(graphbar);graph_toggles.pack(side='right')
        style.configure('HiddenGraph.TButton',background='#39424f',foreground=TEXT,padding=(8,7))
        style.map('HiddenGraph.TButton',background=[('active','#4b5665')])
        self.graph_visibility=[True,True,True,False];self.graph_buttons=[]
        for index,label in enumerate(('Glide Path','Localizer','AoA/Groundspeed')):
            button=ttk.Button(graph_toggles,text=label,style='Selected.TButton',command=lambda index=index:self.toggle_graph(index))
            self.graph_buttons.append(button)
        for button in reversed(self.graph_buttons):button.pack(side='right',padx=3)
        self.black_box_btn=ttk.Button(graph_toggles,text='Black Box',style='HiddenGraph.TButton',command=lambda:self.toggle_graph(3))
        self.black_box_btn.pack(side='right',padx=3);self.graph_buttons.append(self.black_box_btn)
        self.black_box_metrics={key:tk.BooleanVar(value=key in ('vertical_speed','bank','pitch')) for key in BLACK_BOX_METRICS}
        self.black_box_selector=ttk.Menubutton(graph_toggles,text='Black Box Items ▾')
        menu=tk.Menu(self.black_box_selector,tearoff=False,background=PANEL,foreground=TEXT)
        for key,(label,unit,color) in BLACK_BOX_METRICS.items():
            menu.add_checkbutton(label=label,variable=self.black_box_metrics[key],command=self.redraw)
        self.black_box_selector.configure(menu=menu)
        self.toolbar.pack(side='left')
        self.status=tk.StringVar()
        self.build_settings();self.pages.bind('<<NotebookTabChanged>>',self.page_changed)
        self.protocol('WM_DELETE_WINDOW',self.close_app)
        self.row_attempts={};draw(self.fig,None,self.settings);self.canvas.draw();self.after(100,self.poll)
        self.animations=ApplicationAnimations(self)
        self.show_startup_splash()

    def show_startup_splash(self):
        self.startup_splash=None
        try:
            accepted=json.loads(AGREEMENT_PATH.read_text()).get('accepted') is True
        except (OSError,ValueError,AttributeError):accepted=False
        if accepted:
            self.deiconify();return
        splash=tk.Toplevel(self);self.startup_splash=splash
        splash.title('Wire Judge');splash.configure(bg=BG);splash.minsize(760,640)
        width,height=960,760
        x=max(0,(self.winfo_screenwidth()-width)//2);y=max(0,(self.winfo_screenheight()-height)//2)
        splash.geometry(f'{width}x{height}+{x}+{y}');splash.iconphoto(True,self.app_icon)
        splash.protocol('WM_DELETE_WINDOW',self.destroy)
        panel=tk.Canvas(splash,bg=BG,highlightthickness=0,borderwidth=0)
        panel.pack(fill='both',expand=True);panel._splash_background=True
        icon_scale=max(1,(max(self.app_icon.width(),self.app_icon.height())+127)//128)
        self.splash_icon=self.app_icon.subsample(icon_scale,icon_scale)
        def layout_terms(event):
            panel.delete('splash-content');center=event.width/2;y=28
            panel.create_image(center,y,image=self.splash_icon,anchor='n',tags='splash-content')
            y+=self.splash_icon.height()+18
            title=panel.create_text(center,y,text=f'Wire Judge V{APP_VERSION}',font=('Helvetica',32,'bold'),fill=TEXT,anchor='n',tags='splash-content')
            y=panel.bbox(title)[3]+8
            credit=panel.create_text(center,y,text='by: STRAYDOG0626',font=('Helvetica',16),fill=MUTED,anchor='n',tags='splash-content')
            y=panel.bbox(credit)[3]+26
            for paragraph in STARTUP_TERMS:
                item=panel.create_text(center,y,text=paragraph,font=('Helvetica',12 if event.height<700 else 14),width=max(200,event.width-160),justify='center',fill=TEXT,anchor='n',tags='splash-content')
                y=panel.bbox(item)[3]+18
        panel.bind('<Configure>',layout_terms)
        self.agree_value=tk.BooleanVar(value=False)
        ttk.Style(self).configure('Startup.TCheckbutton',font=('Helvetica',14))
        self.agree_checkbox=ttk.Checkbutton(panel,text='I Agree',style='Startup.TCheckbutton',variable=self.agree_value,command=self.accept_startup_terms)
        self.agree_checkbox.place(relx=.5,rely=1,anchor='s',y=-28)
        splash.grab_set();self.agree_checkbox.focus_set()

    def accept_startup_terms(self):
        if not self.agree_value.get():return
        try:
            AGREEMENT_PATH.parent.mkdir(parents=True,exist_ok=True)
            temporary=AGREEMENT_PATH.with_suffix('.tmp')
            temporary.write_text(json.dumps({'accepted':True,'app_version':APP_VERSION},indent=2))
            temporary.replace(AGREEMENT_PATH)
        except OSError as error:
            messagebox.showwarning('Could not save agreement',f'You can continue, but the agreement may appear again next time.\n\n{error}',parent=self.startup_splash)
        self.startup_splash.grab_release();self.startup_splash.destroy();self.startup_splash=None
        self.setting_variables['agreement'].set(True)
        self.deiconify();self.lift()

    def close_app(self):
        if self.editor_page.confirm_context_change():self.destroy()

    def sync_figure_size(self):
        self.canvas.request_resize()

    def set_busy(self,value,status):
        self.busy=value;self.status.set(status)
        self.open_btn.configure(state='disabled' if value else 'normal')
        self.pages.tab(self.settings_page,state='disabled' if value else 'normal')
        self.save_settings_btn.configure(state='disabled' if value else 'normal')
        self.carrier_btn.configure(state='disabled' if value or not self.tracks else 'normal')
        self.wire_select.configure(state='disabled' if value or self.selected is None else 'readonly')
        for button in self.case_buttons:button.configure(state='disabled' if value else 'normal')
        self.pages.tab(self.editor_page,state='disabled' if value else 'normal')
        self.editor_page.refresh()
        if value:self.replay_map.pause()
        elif self.replay_map.active:self.replay_map.refresh()
        self.update_input_buttons()

    def update_input_buttons(self):
        self.open_btn.configure(style='Selected.TButton' if self.filename is not None else 'NeedsInput.TButton')
        self.carrier_btn.configure(style='Selected.TButton' if self.carrier is not None else 'NeedsInput.TButton')

    def work(self,kind,fn):
        def run():
            try:self.messages.put((kind,fn(),None))
            except Exception as e:self.messages.put((kind,None,str(e)))
        threading.Thread(target=run,daemon=True).start()

    def poll(self):
        try:
            kind,value,error=self.messages.get_nowait()
            if error:
                self.set_busy(False,'Could not complete '+kind+'.');messagebox.showerror('Wire Judge',error,parent=self)
            elif kind=='load':
                self.filename,(self.tracks,info),digest=value;self.annotations=Annotations(ANNOTATIONS_DIR/(digest+'.json'));self.edits=AttemptEdits(ANNOTATIONS_DIR/(digest+'_attempts.json'));self.auto_attempts=[];self.attempts=[];self.selected=None;self.carrier=None;self.editor_page.reset();self.populate();self.redraw()
                self.show_tabs();self.set_busy(False,'Replay loaded. Select the correct carrier unit.')
                if not self.tracks:messagebox.showinfo('No motion tracks','This VTR contains no motion tracks. Aircraft approaches cannot be reconstructed from this file.',parent=self)
                else:self.choose_carrier()
            elif kind=='analyze':
                self.auto_attempts=value;self.selected=None;self.apply_edits();self.editor_page.reset();self.set_busy(False,f'{len(self.attempts)} attempts available. Double-click a player to edit their flight log. Glide End marks where approach judging ends.')
                children=self.tree.get_children()
                for parent in children:
                    child=self.tree.get_children(parent)
                    if child:self.tree.selection_set(child[-1]);self.tree.see(child[-1]);break
        except queue.Empty:pass
        self.after(100,self.poll)

    def open_file(self):
        appdata=os.environ.get('APPDATA') if os.name=='nt' else None
        initialdir=Path(appdata) if appdata else Path.home()
        if appdata:
            replays=initialdir/'Boundless Dynamics, LLC'/'VTOLVR'/'SaveData'/'Replays'
            if replays.is_dir():initialdir=replays
        if not initialdir.is_dir():initialdir=Path.home()
        path=filedialog.askopenfilename(parent=self,title='Open native VTOL VR replay',initialdir=str(initialdir),filetypes=[('VTOL VR Replay','*.vtr'),('All files','*')])
        if not path:return
        if not self.editor_page.confirm_context_change():return
        self.set_busy(True,'Decompressing and reading replay motion tracks…');self.work('load',lambda:(Path(path),read_motion(path),replay_digest(path)))

    def choose_carrier(self):
        if not self.tracks or self.busy:return
        if not self.editor_page.confirm_context_change():return
        if self.carrier_selection is not None:self.carrier_selection.destroy()
        self.pages.pack_forget()
        dialog=ttk.Frame(self.content);dialog.pack(fill='both',expand=True);self.carrier_selection=dialog
        ttk.Label(dialog,text='Search and select the actual carrier unit',font=('Helvetica',14,'bold'),padding=16).pack(anchor='w')
        searchrow=ttk.Frame(dialog,padding=(16,0));searchrow.pack(fill='x')
        ttk.Label(searchrow,text='Search:').pack(side='left',padx=(0,8))
        query=tk.StringVar();entry=ttk.Entry(searchrow,textvariable=query);entry.pack(side='left',fill='x',expand=True);entry.focus_set()
        all_units=tk.BooleanVar(value=False);ttk.Checkbutton(dialog,text='Show all unit types',variable=all_units).pack(anchor='w',padx=16,pady=8)
        # Reserve footer space before packing the expanding table.
        footer=ttk.Frame(dialog,padding=(16,8,16,16));footer.pack(side='bottom',fill='x')
        ttk.Label(footer,text='Offsets use this unit’s native origin and rotation.',foreground=MUTED).pack(anchor='w',pady=(0,8))
        frame=ttk.Frame(dialog);frame.pack(fill='both',expand=True,padx=16)
        tree=ttk.Treeview(frame,columns=('id','type','samples'),show='tree headings');tree.heading('#0',text='Unit');tree.heading('id',text='Track ID');tree.heading('type',text='Type');tree.heading('samples',text='Samples');tree.column('#0',width=370)
        for key in ('id','type','samples'):tree.column(key,width=80,stretch=False)
        tree.pack(side='left',fill='both',expand=True);sb=ttk.Scrollbar(frame,command=tree.yview);sb.pack(side='right',fill='y');tree.configure(yscrollcommand=sb.set)
        lookup={}
        def refresh(*_):
            tree.delete(*tree.get_children());lookup.clear();text=query.get().casefold()
            for tr in self.tracks:
                if not all_units.get() and tr['type']!=4:continue
                if text not in (tr['name']+' '+str(tr['id'])).casefold():continue
                iid=str(tr['id']);lookup[iid]=tr;tree.insert('', 'end',iid=iid,text=tr['name'] or '(unnamed unit)',values=(tr['id'],tr['type'],len(tr['rows'])))
        def select(*_):
            selection=tree.selection()
            if not selection or self.busy:return
            if not self.editor_page.confirm_context_change():return
            self.carrier=lookup[selection[0]];self.show_tabs();self.reanalyze()
        query.trace_add('write',refresh);all_units.trace_add('write',refresh);tree.bind('<Double-1>',select);tree.bind('<Return>',select)
        buttons=ttk.Frame(footer);buttons.pack(fill='x')
        if self.carrier is not None:ttk.Button(buttons,text='Cancel',command=self.show_tabs).pack(side='left')
        ttk.Button(buttons,text='Use selected carrier',width=22,command=select).pack(side='right');refresh()

    def show_tabs(self):
        if self.carrier_selection is not None:
            self.carrier_selection.destroy();self.carrier_selection=None
        self.pages.pack(fill='both',expand=True)

    def reanalyze(self):
        if self.carrier is None:return
        self.update_settings_readouts()
        self.set_busy(True,'Finding carrier-relative approach attempts…')
        tracks=self.tracks;carrier=self.carrier;settings=self.settings
        self.work('analyze',lambda:analyze(tracks,carrier,settings))

    def populate(self):
        if not hasattr(self,'tree'):return
        self.refresh_scores();self.tree.tag_configure('best',foreground='#6cd9af');self.tree.tag_configure('provisional',foreground='#ffce76')
        old=self.selected;self.tree.delete(*self.tree.get_children());self.row_attempts={};self.row_players={}
        mode=self.attempt_filter.get()
        visible=last_attempts(self.attempts) if mode=='Last attempt' else [a for a in self.attempts if is_best(a,self.scores.get(a.edit_id),self.best_scores)] if mode=='Best attempt' else self.attempts
        groups=defaultdict(list)
        for tr in self.tracks:
            if tr['type']==0 and '(' in tr['name'] and not any(s in tr['name'].upper() for s in ('AV-42','AH-94','AH-99')):groups[player_label(tr['name'])]
        for a in visible:groups[a.player].append(a)
        text=self.player_search.get().strip().casefold();shown=0;selected_row=None
        for n,(player,attempts) in enumerate(sorted(groups.items(),key=lambda p:p[0].casefold())):
            if text and text not in player.casefold() and not any(text in a.aircraft.casefold() for a in attempts):continue
            parent=f'p{n}';self.tree.insert('','end',iid=parent,text=f'{player}  ({len(attempts)})',open=True)
            self.row_players[parent]=player
            for i,a in enumerate(sorted(attempts,key=lambda a:a.start)):
                row=f'{parent}a{i}';self.row_attempts[row]=a;shown+=1
                wire=self.get_wire(a);suffix=('  ·  Bolter' if wire=='Bolter' else '  ·  Wire '+wire) if wire else ''
                score=self.scores.get(a.edit_id)
                if score:suffix+=f'  ·  {score.total:,.1f}'+(' provisional' if not score.complete else '')
                best=is_best(a,score,self.best_scores)
                self.tree.insert(parent,'end',iid=row,text=('★ ' if best else '')+f'{clock(a.start)}  ·  {a.aircraft}'+suffix,tags=('provisional',) if score and not score.complete else ('best',) if best else ())
                if a is old:selected_row=row
        self.count_text.set(f'{shown} shown / {len(self.attempts)} detected attempts')
        if self.score_window and self.score_window.winfo_exists():self.score_window.refresh()
        rows={a.edit_id:row for row,a in self.row_attempts.items()}
        available={a.edit_id for a in self.attempts}
        self.comparison_ids=[key for key in self.comparison_ids if key in available]
        if not self.comparison_ids and selected_row:self.comparison_ids=[self.row_attempts[selected_row].edit_id]
        self.tree.selection_set([rows[key] for key in self.comparison_ids if key in rows])
        if not self.comparison_ids:self.selected=None;self.redraw()

    def apply_edits(self):
        selected_id=self.selected.edit_id if self.selected else None
        self.attempts=self.edits.apply(self.auto_attempts,self.tracks,self.carrier,self.settings)
        self.selected=next((a for a in self.attempts if a.edit_id==selected_id),None)
        self.populate();self.redraw()
        if self.edits.warnings:self.status.set('Some saved intervals could not be applied: '+self.edits.warnings[0])
        if self.score_window and self.score_window.winfo_exists():self.score_window.refresh()

    def open_player_editor(self,event=None):
        if self.busy or self.carrier is None:return 'break'
        row=self.tree.identify_row(event.y) if event is not None else self.tree.focus()
        attempt=self.row_attempts.get(row)
        if attempt is not None:
            self.pages.select(self.replay_map)
            self.replay_map.open_attempt(attempt.entity_id,attempt.start)
            return 'break'
        player=self.row_players.get(row)
        if player:
            self.pages.select(self.editor_page);self.editor_page.select_player(player)
        return 'break'

    def jump_to_replay(self,attempt,timestamp):
        if self.busy or self.carrier is None:return
        self.pages.select(self.replay_map)
        self.replay_map.open_attempt(attempt.entity_id,timestamp)

    def toggle_points(self):
        self.settings.show_data_points=self.points_value.get()
        try:self.settings.save(SETTINGS_PATH)
        except OSError as error:messagebox.showerror('Could not save setting',str(error),parent=self)
        self.redraw(preserve_view=True)

    def toggle_graph(self,index):
        if index==3 and len(self.comparison_ids)>1:return
        self.graph_visibility[index]=not self.graph_visibility[index]
        self.graph_buttons[index].configure(style='Selected.TButton' if self.graph_visibility[index] else 'HiddenGraph.TButton')
        self.redraw()

    def toggle_comparison_row(self,event):
        row=self.tree.identify_row(event.y)
        if row not in self.row_attempts:return
        key=self.row_attempts[row].edit_id
        if event.state & 0x0001:
            if key in self.comparison_ids:self.comparison_ids.remove(key)
            else:self.comparison_ids=(self.comparison_ids+[key])[-MAX_COMPARE_ATTEMPTS:]
        else:self.comparison_ids=[key]
        rows={a.edit_id:row for row,a in self.row_attempts.items()}
        self.tree.focus(row);self.tree.focus_set()
        self.tree.selection_set([rows[key] for key in self.comparison_ids if key in rows])
        return 'break'

    def select_attempt(self,*_):
        rows=[row for row in self.tree.selection() if row in self.row_attempts]
        visible_ids={a.edit_id for a in self.row_attempts.values()}
        hidden=[key for key in self.comparison_ids if key not in visible_ids]
        selected={self.row_attempts[row].edit_id for row in rows}|set(hidden)
        if not selected:
            if not self.tree.selection():self.selected=None;self.comparison_ids=[];self.redraw()
            return
        ordered=[key for key in self.comparison_ids if key in selected]
        ordered.extend(self.row_attempts[row].edit_id for row in rows if self.row_attempts[row].edit_id not in ordered)
        kept=ordered[-MAX_COMPARE_ATTEMPTS:]
        if len(ordered)>MAX_COMPARE_ATTEMPTS:self.tree.selection_set([row for row in rows if self.row_attempts[row].edit_id in kept])
        self.comparison_ids=kept
        focused=self.row_attempts.get(self.tree.focus())
        lookup={a.edit_id:a for a in self.attempts}
        self.selected=focused if focused is not None and focused.edit_id in kept else lookup.get(kept[-1])
        self.redraw()

    def update_compare_icons(self):
        slots={key:index for index,key in enumerate(self.comparison_ids)} if len(self.comparison_ids)>1 else {}
        for row,attempt in self.row_attempts.items():
            self.tree.item(row,image=self.compare_icons[slots[attempt.edit_id]] if attempt.edit_id in slots else '')

    def redraw(self,preserve_view=False):
        view=[(axis.get_xlim(),axis.get_ylim()) for axis in self.fig.axes] if preserve_view else []
        a=self.selected
        self.update_compare_icons()
        self.wire_value.set(self.get_wire(a) if a else '')
        self.wire_select.configure(state='readonly' if a and not self.busy else 'disabled')
        origin=glide_origin_msl_ft(self.carrier,self.settings)
        compared=[];labels=[]
        if a or self.comparison_ids:
            lookup={item.edit_id:item for item in self.attempts}
            compared=[lookup[key] for key in self.comparison_ids if key in lookup] or ([a] if a else [])
            for item in compared:
                own=sorted((other for other in self.attempts if other.player.casefold()==item.player.casefold()),key=lambda other:other.start)
                number=next(i for i,other in enumerate(own,1) if other.edit_id==item.edit_id)
                labels.append(f'{item.player} #{number}')
        comparing=len(compared)>1
        if comparing:self.graph_visibility[3]=False
        self.black_box_btn.configure(state='disabled' if comparing else 'normal',style='Selected.TButton' if self.graph_visibility[3] else 'HiddenGraph.TButton')
        if self.graph_visibility[3]:self.black_box_selector.pack(side='right',padx=3)
        else:self.black_box_selector.pack_forget()
        diagnostics=None
        if self.graph_visibility[3] and a is not None:
            track=next((track for track in self.tracks if track['id']==a.entity_id),None)
            if track is not None:diagnostics=black_box_data(track,a,self.carrier,self.settings)
        if preserve_view:self.toolbar.update()
        else:self.toolbar.new_graph()
        draw(self.fig,compared if compared else a,self.settings,origin,labels=labels,visible_graphs=self.graph_visibility,black_box=diagnostics,
             black_box_metrics=[key for key,variable in self.black_box_metrics.items() if variable.get()])
        if view:
            self.toolbar.push_current()
            for axis,(xlim,ylim) in zip(self.fig.axes,view):axis.set_xlim(xlim);axis.set_ylim(ylim)
            self.toolbar.push_current()
        self.graph_cursor.refresh();self.canvas.draw_idle()

    def get_wire(self,attempt):
        if attempt is None:return ''
        manual=self.annotations.find(self.carrier['id'],attempt) if self.carrier and self.annotations else None
        return manual['wire'] if manual is not None else ('Bolter' if auto_bolter(attempt) else '')

    def set_wire(self,*_):
        if not self.selected or not self.annotations or self.busy:return
        try:self.annotations.set(self.carrier['id'],self.selected,self.wire_value.get())
        except (OSError,ValueError) as error:
            self.wire_value.set(self.get_wire(self.selected));messagebox.showerror('Could not save wire',str(error),parent=self);return
        self.populate();self.redraw();self.editor_page.refresh();self.status.set('Manual wire choice saved for this landing.')
        if self.score_window and self.score_window.winfo_exists():self.score_window.refresh()

    def refresh_scores(self):
        origin=glide_origin_msl_ft(self.carrier,self.settings)
        self.scores={a.edit_id:score_attempt(a,self.get_wire(a),self.settings,origin) for a in self.attempts}
        self.best_scores=best_by_player(self.attempts,self.scores)

    def page_changed(self,event=None):
        self.replay_map.set_active(self.pages.select()==str(self.replay_map))
        if self.pages.select()==str(self.score_window):self.score_window.refresh()
        elif self.pages.select()==str(self.approach_page):self.after_idle(self.sync_figure_size)
        elif self.pages.select()==str(self.editor_page):self.editor_page.refresh()

    def show_scores(self):
        self.score_window.refresh();self.pages.select(self.score_window)

    def show_settings(self):
        if not self.busy:self.pages.select(self.settings_page)

    def change_case(self,*_):
        if self.busy:return
        previous=self.settings.recovery_case;chosen=3 if self.case_value.get()=='Case 3' else 1
        if chosen==previous:return
        if not self.editor_page.confirm_context_change():self.case_value.set(f'Case {previous}');return
        try:
            values=asdict(self.settings);values['recovery_case']=chosen;settings=Settings(**values);settings.validate()
            start=glide_start_nm(settings,glide_origin_msl_ft(self.carrier,settings))
            if start is None or settings.scoring_changeover_nm>=start:raise ValueError('Glide End must be closer to the carrier than Glide Start for the selected case.')
            settings.save(SETTINGS_PATH)
        except (ValueError,OSError) as error:
            self.case_value.set(f'Case {previous}');messagebox.showerror('Could not change recovery case',str(error),parent=self);return
        self.settings=settings;self.selected=None;self.populate();self.redraw();self.update_settings_readouts();self.score_window.refresh()
        if self.carrier is not None:self.reanalyze()
        else:self.status.set(f'Case {chosen} selected.')

    def clear_cache(self):
        if self.busy:return
        if not messagebox.askyesno('Clear Cache?', 'Remove saved wire annotations and attempt edits for all replays, including unsaved attempt edits? Settings and replay files will be kept.',parent=self):return
        errors=[]
        paths=set()
        try:
            paths.update(ANNOTATIONS_DIR.glob('*.json'))
            paths.update(ANNOTATIONS_DIR.glob('*.tmp'))
        except OSError as exc:errors.append(str(exc))
        for cache in (self.annotations,self.edits):
            if cache is not None:
                paths.add(cache.path)
                paths.add(cache.path.with_suffix('.tmp'))
        for path in sorted(paths):
            try:path.unlink(missing_ok=True)
            except OSError as exc:errors.append(str(exc))
        if self.annotations:self.annotations=Annotations(self.annotations.path)
        if self.edits:self.edits=AttemptEdits(self.edits.path)
        self.selected=None;self.comparison_ids=[]
        if self.carrier is not None:self.apply_edits();self.editor_page.reset()
        else:self.editor_page.reset();self.populate();self.redraw();self.score_window.refresh()
        if errors:messagebox.showerror('Could not clear all cache files','\n'.join(errors),parent=self)
        else:self.status.set('Replay annotations and attempt edits cleared.')

    def build_settings(self):
        dialog=self.settings_page
        buttons=ttk.Frame(dialog,padding=16);buttons.pack(side='bottom',fill='x')
        tabs=ttk.Notebook(dialog);tabs.pack(fill='both',expand=True,padx=12,pady=12)
        general=ttk.Frame(tabs,padding=16);scoring_page=ttk.Frame(tabs,padding=16);carrier_page=ttk.Frame(tabs,padding=16)
        application_page=ttk.Frame(tabs,padding=16)
        tabs.add(general,text='Approach & Graphs');tabs.add(scoring_page,text='Point Values')
        tabs.add(application_page,text='Application');tabs.add(carrier_page,text='Carrier Config')
        self.settings_tabs=tabs;variables={};self.setting_variables=variables
        def tolerance(settings):return max(8-settings.aoa_min_deg,settings.aoa_max_deg-8)
        def agreement_accepted():
            try:return json.loads(AGREEMENT_PATH.read_text()).get('accepted') is True
            except (OSError,ValueError,AttributeError):return False
        def displayed(settings,key):
            if key=='agreement':return agreement_accepted()
            if key=='aoa_tolerance_deg':return tolerance(settings)
            if key=='case1_glide_start_nm':return glide_start_nm(Settings(**{**asdict(settings),'recovery_case':1}),glide_origin_msl_ft(self.carrier,settings)) or 0
            return getattr(settings,key)
        self.auto_start_display=f'{displayed(self.settings,"case1_glide_start_nm"):.12g}'
        def entry(group,key,label,row,pady=6):
            ttk.Label(group,text=label).grid(row=row,column=0,sticky='w',pady=pady)
            variable=tk.StringVar(value=f'{displayed(self.settings,key):.12g}');variables[key]=variable
            ttk.Entry(group,textvariable=variable,width=12).grid(row=row,column=1,sticky='e',padx=(16,0),pady=pady)
        self.opacity_sliders={}
        def setting_slider(group,key,label,row,color=GREEN,minimum=0,maximum=1,percent=True):
            ttk.Label(group,text=label,foreground=color).grid(row=row,column=0,sticky='w',pady=1)
            variable=tk.DoubleVar(value=getattr(self.settings,key));variables[key]=variable
            control=ttk.Frame(group);control.grid(row=row,column=1,sticky='ew',padx=(16,0),pady=1)
            control.columnconfigure(0,weight=1)
            percentage=tk.StringVar()
            def update_percentage(*_):percentage.set(f'{variable.get():.0%}' if percent else f'{variable.get():.1f}')
            variable.trace_add('write',update_percentage);update_percentage()
            slider_style=f'{key}.Horizontal.TScale';style=ttk.Style(self)
            style.configure(slider_style,background=color,troughcolor=PANEL)
            style.map(slider_style,background=[('active',color)])
            scale=ttk.Scale(control,from_=minimum,to=maximum,variable=variable,orient='horizontal',length=140,style=slider_style)
            scale.grid(row=0,column=0,sticky='ew')
            if percent:self.opacity_sliders[key]=scale
            else:self.line_width_slider=scale
            ttk.Label(control,textvariable=percentage,width=5,anchor='e').grid(row=0,column=1,padx=(6,0))
        def reset_start():
            try:
                values=asdict(self.settings)
                for key in ('offset_x','offset_y','offset_z','runway_deg','glide_deg'):values[key]=float(variables[key].get())
                geometry=Settings(**values)
                if not .1<=geometry.glide_deg<=15:raise ValueError('Glide slope must be between 0.1° and 15°.')
                start=target_intercept_nm(geometry,glide_origin_msl_ft(self.carrier,geometry))
                if start is None or not 0<start<=10:raise ValueError('The configured carrier/glide geometry has no 600 ft intercept within 10 NM.')
                variables['case1_glide_start_nm'].set(f'{start:.12g}')
            except (ValueError,TypeError) as error:messagebox.showerror('Could not reset Glide Start',str(error),parent=self)
        self.reset_case1_start=reset_start
        ttk.Style(self).configure('Square.TButton',padding=(4,3))
        self.reset_start_image=tk.PhotoImage(width=18,height=18)
        for y in range(18):
            for x in range(18):
                radius=(x-8)**2+(y-9)**2
                if (35<=radius<=60 and not (x>=10 and y<=6)) or (10<=x<=15 and 2<=y<=7 and x+y>=17):self.reset_start_image.put(TEXT,(x,y))
        groups=(('Graph Settings',{'graph_range_nm':'Case 1 Render Distance (NM)','case3_graph_range_nm':'Case 3 Render Distance (NM)'}),
                ('Glide Limits',{'case1_glide_start_nm':'Case 1 Glide Start (NM)','case3_glide_start_nm':'Case 3 Glide Start (NM)','scoring_changeover_nm':'Glide End (NM)',
                                 'glide_tolerance_deg':'Glide slope +/- (°)','localizer_tolerance_deg':'Localizer +/- (°)','aoa_tolerance_deg':'AoA +/- (°)'}),
                ('CASE 3 Limits',{'case3_platform_alt_ft':'Platform Alt +/- (ft)','case3_platform_speed_knots':'Platform Spd +/- (Knots)','case3_leg1_speed_knots':'Leg 1 Speed (Knots)','case3_speed_deadzone_nm':'Speed Changeover Deadzone (NM)','case3_speed_changeover_shift_nm':'Changeover Shift (NM)','case3_leg2_speed_knots':'Leg 2 Speed (Knots)','case3_platform_start_nm':'Platform Start (NM)','case3_platform_end_nm':'Platform End (NM)'}),
                ('Replay Settings',{'replay_trail_fade_sec':'Trail Fade (sec)'}))
        general.columnconfigure(0,weight=1);general.columnconfigure(1,weight=1)
        for section,(heading,mapping) in enumerate(groups):
            group=ttk.LabelFrame(general,text=heading,padding=(12,8));group.grid(row=section//2,column=section%2,sticky='new',padx=(0,12) if section%2==0 else 0,pady=(0,12));group.columnconfigure(0,weight=1)
            for i,(key,label) in enumerate(mapping.items()):
                entry(group,key,label,i,pady=0 if heading=='Graph Settings' else 4 if heading=='CASE 3 Limits' else 6)
                if key=='case1_glide_start_nm':
                    self.case1_reset_btn=ttk.Button(group,image=self.reset_start_image,style='Square.TButton',command=reset_start)
                    self.case1_reset_btn.grid(row=i,column=2,padx=(6,0))
            if heading=='Replay Settings':
                group.columnconfigure(1,weight=1)
                setting_slider(group,'replay_procedure_opacity','Procedure Markings',len(mapping),START_END_COLOR)
            if heading=='Graph Settings':
                group.columnconfigure(1,weight=1)
                for row,(key,label) in enumerate((('limit_outline_opacity','Limit Outline'),('limit_shading_opacity','Limit Shading'),('limit_center_opacity','Limit Center'),('start_end_opacity','Start/End')),len(mapping)):
                    setting_slider(group,key,label,row,START_END_COLOR if key=='start_end_opacity' else GREEN)
                setting_slider(group,'graph_line_width','Line Thickness',len(mapping)+4,color=TEXT,minimum=.5,maximum=5,percent=False)
                variables['show_graph_key']=tk.BooleanVar(value=self.settings.show_graph_key)
                ttk.Checkbutton(group,text='Show Key',variable=variables['show_graph_key']).grid(row=len(mapping)+5,column=0,columnspan=2,sticky='w',pady=1)
                variables['show_timestamp']=tk.BooleanVar(value=self.settings.show_timestamp)
                ttk.Checkbutton(group,text='Show Timestamp',variable=variables['show_timestamp']).grid(row=len(mapping)+6,column=0,columnspan=2,sticky='w',pady=1)
        application=ttk.LabelFrame(application_page,text='Application',padding=(16,12));application.pack(fill='x');application.columnconfigure(1,weight=1)
        variables['agreement']=tk.BooleanVar(value=agreement_accepted())
        ttk.Checkbutton(application,text='Agreement',variable=variables['agreement']).grid(row=0,column=0,columnspan=2,sticky='w',pady=6)
        variables['random_animations']=tk.BooleanVar(value=self.settings.random_animations)
        self.animation_toggle=ttk.Button(application,text='Random Animations',command=lambda:variables['random_animations'].set(not variables['random_animations'].get()))
        self.animation_toggle.grid(row=1,column=0,columnspan=2,sticky='w',pady=6)
        def animation_toggle_style(*_):self.animation_toggle.configure(style='Selected.TButton' if variables['random_animations'].get() else 'TButton')
        variables['random_animations'].trace_add('write',animation_toggle_style);animation_toggle_style()
        entry(application,'random_animation_frequency_sec','Random Animation Frequency (sec)',2)
        setting_slider(application,'animation_opacity','Animation Opacity',3,START_END_COLOR)
        destinations=ttk.LabelFrame(application_page,text='Animations by Tab',padding=(16,12));destinations.pack(fill='x',pady=(16,0))
        for row,(key,label) in enumerate((('animation_approach','Approach Viewer'),('animation_scores','Scoreboard'),('animation_editor','Attempt Editor'),('animation_settings','Settings'))):
            variables[key]=tk.BooleanVar(value=getattr(self.settings,key))
            ttk.Checkbutton(destinations,text=label,variable=variables[key]).grid(row=row,column=0,sticky='w',pady=5)
        ttk.Label(carrier_page,text='Do not change. Advance use only.',foreground='#f5a65b',font=('Helvetica',9)).pack(anchor='w',pady=(0,8))
        carrier=ttk.LabelFrame(carrier_page,text='Carrier ILS',padding=(16,12));carrier.pack(fill='x');carrier.columnconfigure(0,weight=1)
        for i,(key,label) in enumerate({'offset_x':'X Offset','offset_y':'Y Offset','offset_z':'Z Offset','runway_deg':'Runway Offset','glide_deg':'Glide Slope Angle'}.items()):entry(carrier,key,label,i)
        ttk.Label(carrier_page,text='X: right · Y: up · Z: forward',foreground=MUTED,padding=(0,12)).pack(anchor='w')
        def readouts(*_):
            if self.settings.case1_glide_start_nm==0 and variables['case1_glide_start_nm'].get()==self.auto_start_display:
                self.auto_start_display=f'{displayed(self.settings,"case1_glide_start_nm"):.12g}'
                variables['case1_glide_start_nm'].set(self.auto_start_display)
        self.update_settings_readouts=readouts
        sections=(('CASE 1 Points',{'scoring_loc_points':'Localizer','scoring_glide_points':'Glide','scoring_aoa_points':'AoA'}),
                  ('CASE 3 Points',{'scoring_case3_position_points':'Platform Position Accuracy','scoring_case3_speed_points':'Platform Speed Accuracy','scoring_case3_loc_points':'Localizer','scoring_case3_glide_points':'Glide','scoring_case3_aoa_points':'AoA'}),
                  ('Landing points',{'scoring_bolter_points':'Bolter','scoring_wire1_points':'1 Wire','scoring_wire2_points':'2 Wire','scoring_wire3_points':'3 Wire','scoring_wire4_points':'4 Wire'}))
        scoring_page.columnconfigure(0,weight=1);scoring_page.columnconfigure(1,weight=1);totals={}
        for section,(heading,mapping) in enumerate(sections):
            group=ttk.LabelFrame(scoring_page,text=heading,padding=(12,8));group.grid(row=section//2,column=section%2,sticky='new',padx=(0,12) if section%2==0 else 0,pady=(0,12));group.columnconfigure(0,weight=1)
            for i,(key,label) in enumerate(mapping.items()):entry(group,key,label,i)
            if section<2:
                total=tk.StringVar();totals[section]=total
                ttk.Label(group,textvariable=total,font=('Helvetica',11,'bold')).grid(row=len(mapping),column=0,columnspan=2,sticky='w',pady=8)
        self.approach_totals=totals
        def update_totals(*_):
            for case_index,(_,mapping) in enumerate(sections[:2]):
                try:totals[case_index].set(f'Total: {sum(float(variables[key].get()) for key in mapping):,.0f}')
                except ValueError:totals[case_index].set('Total: —')
        for _,mapping in sections[:2]:
            for key in mapping:variables[key].trace_add('write',update_totals)
        update_totals()
        def save():
            try:
                values=asdict(self.settings);entered={k:float(v.get()) for k,v in variables.items() if k!='agreement'};half=entered.pop('aoa_tolerance_deg')
                if not 0<half<=172:raise ValueError('AoA +/- must be positive and at most 172°.')
                entered['show_graph_key']=bool(variables['show_graph_key'].get())
                entered['show_timestamp']=bool(variables['show_timestamp'].get())
                for key in ('random_animations','animation_approach','animation_scores','animation_editor','animation_settings'):
                    entered[key]=bool(variables[key].get())
                values.update(entered);values.update(aoa_min_deg=8-half,aoa_max_deg=8+half);settings=Settings(**values);settings.validate()
                target=glide_start_nm(settings,glide_origin_msl_ft(self.carrier,settings))
                if target is None or settings.scoring_changeover_nm>=target:raise ValueError('Glide End must be closer to the carrier than Glide Start.')
                if not self.editor_page.confirm_context_change():return
                settings.save(SETTINGS_PATH)
                AGREEMENT_PATH.parent.mkdir(parents=True,exist_ok=True)
                temporary=AGREEMENT_PATH.with_suffix('.tmp')
                temporary.write_text(json.dumps({'accepted':bool(variables['agreement'].get()),'app_version':APP_VERSION},indent=2))
                temporary.replace(AGREEMENT_PATH)
            except (ValueError,TypeError,OSError) as e:messagebox.showerror('Invalid settings',str(e),parent=self);return
            self.settings=settings;self.points_value.set(settings.show_data_points);self.selected=None;self.redraw();self.status.set('Settings saved and applied.');readouts();self.score_window.refresh()
            update_button_styles()
            if self.carrier is not None:self.reanalyze()
        def restore(settings):
            for k,v in variables.items():v.set(f'{displayed(settings,k):.12g}')
            self.auto_start_display=variables['case1_glide_start_nm'].get()
        self.restore_defaults_btn=ttk.Button(buttons,text='Restore Defaults',command=lambda:restore(Settings()));self.restore_defaults_btn.pack(side='left')
        self.clear_cache_btn=ttk.Button(buttons,text='Clear Cache',command=self.clear_cache);self.clear_cache_btn.pack(side='left',padx=8)
        self.reset_settings_btn=ttk.Button(buttons,text='Reset Changes',command=lambda:restore(self.settings));self.reset_settings_btn.pack(side='right')
        self.save_settings_btn=ttk.Button(buttons,text='Save & Apply',command=save);self.save_settings_btn.pack(side='right',padx=8)
        def update_button_styles(*_):
            try:changed=any(abs(float(variable.get())-float(displayed(self.settings,key)))>1e-10 for key,variable in variables.items())
            except (ValueError,TypeError,tk.TclError):changed=True
            self.save_settings_btn.configure(style='Selected.TButton' if changed else 'TButton')
            self.reset_settings_btn.configure(style='NeedsInput.TButton' if changed else 'TButton')
        for variable in variables.values():variable.trace_add('write',update_button_styles)
        update_button_styles()

if __name__=='__main__':WireJudge().mainloop()
