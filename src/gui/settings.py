"""Diálogo de configurações: IA, voz, áudio e player."""
import re

import httpx
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QSpinBox, QTabWidget, QVBoxLayout,
                               QWidget)

# Presets de provedores OpenAI-compatíveis.
# base_url/modelos preenchem os campos ao selecionar; "descobrir" consulta
# o endpoint /models do servidor pra listar os modelos disponíveis.
PROVIDER_PRESETS = [
    {
        "name": "Personalizado",
        "base_url": "",
        "models": [],
        "discover": False,
        "hint": "Digite manualmente o endpoint, modelo e chaves.",
    },
    {
        "name": "Gemini API",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": ["gemini-3.1-flash-lite", "gemini-2.5-flash",
                   "gemini-3.5-flash-lite"],
        "discover": False,
        "hint": "Requires API key. Endpoint OpenAI-compatível do Google.",
    },
    {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        "discover": True,
        "hint": "Requires API key.",
    },
    {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"],
        "discover": True,
        "hint": "Requires API key.",
    },
    {
        "name": "Ollama (local)",
        "base_url": "http://localhost:11434/v1",
        "models": ["gemma3:1b", "gemma3:4b", "llama3.2:1b", "llama3.2:3b"],
        "discover": True,
        "hint": "Servidor local. Sem chave. Use 'Buscar' para listar modelos.",
    },
    {
        "name": "LM Studio (local)",
        "base_url": "http://localhost:1234/v1",
        "models": ["google/gemma-3-1b-it", "microsoft/phi-4-mini",
                   "qwen3-1.7b"],
        "discover": True,
        "hint": "Servidor local. Sem chave. Use 'Buscar' para listar modelos.",
    },
    {
        "name": "vLLM / llama.cpp (local)",
        "base_url": "http://localhost:8000/v1",
        "models": [],
        "discover": True,
        "hint": "Servidor local. Use 'Buscar' para listar modelos.",
    },
]


class SettingsDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.cfg = cfg
        self.resize(600, 560)

        tabs = QTabWidget()
        tabs.addTab(self._tab_brain(), "Cérebro (LLM)")
        tabs.addTab(self._tab_voice(), "Voz")
        tabs.addTab(self._tab_locucao(), "Locução & Áudio")
        tabs.addTab(self._tab_player(), "Player")

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # ---------- Cérebro ----------
    def _tab_brain(self):
        b = self.cfg["brain"]
        api = b.get("api", {})

        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["api", "template"])
        self.cb_mode.setCurrentText(b.get("mode", "template"))

        # --- provedor ---
        self.cb_provider = QComboBox()
        for p in PROVIDER_PRESETS:
            self.cb_provider.addItem(p["name"])
        self.lbl_hint = QLabel()
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setStyleSheet("color: #888; font-size: 11px;")

        # --- endpoint / modelo ---
        self.ed_base_url = QLineEdit(api.get("base_url", ""))
        self.ed_base_url.setPlaceholderText("https://... ou http://localhost:porta/v1")

        self.cb_model = QComboBox()
        self.cb_model.setEditable(True)
        cur_model = api.get("model", "")
        if cur_model:
            self.cb_model.addItem(cur_model)
            self.cb_model.setCurrentText(cur_model)

        self.btn_discover = QPushButton("Buscar modelos")
        self.btn_discover.setToolTip(
            "Consulta {base_url}/models do servidor e lista os modelos disponíveis")
        self.btn_discover.clicked.connect(self._discover_models)
        model_row = QHBoxLayout()
        model_row.addWidget(self.cb_model, 1)
        model_row.addWidget(self.btn_discover)

        self.ed_fallback = QLineEdit(api.get("fallback_model", ""))
        self.ed_fallback.setPlaceholderText("(vazio = desligado)")

        # --- seleção de provedor ---
        self.cb_provider.currentIndexChanged.connect(self._on_provider)
        self._match_provider(api.get("base_url", ""), api.get("model", ""))

        # --- avançado ---
        self.sp_temp = QDoubleSpinBox()
        self.sp_temp.setRange(0.0, 2.0)
        self.sp_temp.setSingleStep(0.1)
        self.sp_temp.setValue(float(b.get("temperature", 0.9)))

        self.sp_timeout = QSpinBox()
        self.sp_timeout.setRange(1, 300)
        self.sp_timeout.setSuffix(" s")
        self.sp_timeout.setValue(int(api.get("timeout_sec", 15)))

        self.sp_api_timeout = QSpinBox()
        self.sp_api_timeout.setRange(1, 300)
        self.sp_api_timeout.setSuffix(" s")
        self.sp_api_timeout.setValue(int(api.get("api_timeout_sec", 20)))

        self.sp_cooldown = QSpinBox()
        self.sp_cooldown.setRange(0, 3600)
        self.sp_cooldown.setSuffix(" s")
        self.sp_cooldown.setValue(int(api.get("key_cooldown_sec", 60)))

        self.ed_keys = QPlainTextEdit("\n".join(api.get("keys") or []))
        self.ed_keys.setPlaceholderText(
            "Uma chave por linha. Provedores locais podem deixar vazio.")

        self.ed_persona = QPlainTextEdit(b.get("persona", ""))
        self.ed_persona.setMaximumHeight(90)

        # ---------- layout ----------
        box_provider = QGroupBox("Provedor (LLM)")
        f1 = QFormLayout(box_provider)
        f1.addRow("Provedor", self.cb_provider)
        f1.addRow("Endpoint (base_url)", self.ed_base_url)
        f1.addRow("Modelo", model_row)
        f1.addRow("Modelo fallback", self.ed_fallback)
        f1.addRow("", self.lbl_hint)

        box_adv = QGroupBox("Avançado")
        f2 = QFormLayout(box_adv)
        adv_row = QHBoxLayout()
        adv_row.addWidget(self.cb_mode)
        adv_row.addWidget(QLabel("Temperatura:"))
        adv_row.addWidget(self.sp_temp)
        adv_row.addStretch(1)
        f2.addRow("Modo / Temperatura", adv_row)
        t_row = QHBoxLayout()
        t_row.addWidget(QLabel("Chamada:"))
        t_row.addWidget(self.sp_timeout)
        t_row.addWidget(QLabel("Global:"))
        t_row.addWidget(self.sp_api_timeout)
        t_row.addWidget(QLabel("Cooldown:"))
        t_row.addWidget(self.sp_cooldown)
        t_row.addStretch(1)
        f2.addRow("Timeouts", t_row)
        f2.addRow("Chaves API", self.ed_keys)
        f2.addRow("Persona", self.ed_persona)

        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(box_provider)
        v.addWidget(box_adv)
        v.addStretch(1)
        return w

    # ---------- provedor ----------
    def _match_provider(self, base_url, model):
        """Tenta identificar o provedor a partir da config atual."""
        for i, p in enumerate(PROVIDER_PRESETS):
            if p["name"] == "Personalizado":
                continue
            if p["base_url"] and base_url.rstrip("/") == p["base_url"].rstrip("/"):
                self.cb_provider.setCurrentIndex(i)
                break
        else:
            self.cb_provider.setCurrentIndex(0)

    def _on_provider(self, idx):
        p = PROVIDER_PRESETS[idx]
        if p["name"] != "Personalizado":
            self.ed_base_url.setText(p["base_url"])
        self.lbl_hint.setText(p["hint"])
        # atualiza sugestões de modelo (mantém o atual se ainda válido)
        cur = self.cb_model.currentText()
        if p["name"] == "Personalizado":
            if cur and self.cb_model.findText(cur) == -1:
                self.cb_model.addItem(cur)
            return
        self.cb_model.blockSignals(True)
        self.cb_model.clear()
        if p["models"]:
            for m in p["models"]:
                self.cb_model.addItem(m)
            if cur in p["models"]:
                self.cb_model.setCurrentText(cur)
        elif cur:
            self.cb_model.addItem(cur)
            self.cb_model.setCurrentText(cur)
        self.cb_model.blockSignals(False)

    def _discover_models(self):
        """Consulta GET {base_url}/models e preenche o combo de modelo."""
        base = self.ed_base_url.text().strip().rstrip("/")
        if not base:
            QMessageBox.information(
                self, "Buscar modelos",
                "Preencha o endpoint (base_url) antes de buscar modelos.")
            return
        keys = [k.strip() for k in self.ed_keys.toPlainText().splitlines()
                if k.strip()]
        headers = {"Content-Type": "application/json"}
        if keys:
            headers["Authorization"] = f"Bearer {keys[0]}"
        self.btn_discover.setEnabled(False)
        self.btn_discover.setText("Buscando...")
        try:
            r = httpx.get(f"{base}/models", headers=headers, timeout=10)
            if r.status_code == 404:
                QMessageBox.warning(
                    self, "Buscar modelos",
                    f"Este endpoint não suporta listagem de modelos "
                    f"(GET {base}/models retornou 404).\nDigite o modelo "
                    f"manualmente no campo acima.")
                return
            r.raise_for_status()
            data = r.json()
            ids = [m.get("id") for m in data.get("data", []) if m.get("id")]
            ids = sorted(set(ids))
            if not ids:
                QMessageBox.information(
                    self, "Buscar modelos",
                    "Nenhum modelo encontrado na resposta do servidor.")
                return
            cur = self.cb_model.currentText()
            self.cb_model.blockSignals(True)
            self.cb_model.clear()
            for m in ids:
                self.cb_model.addItem(m)
            if cur in ids:
                self.cb_model.setCurrentText(cur)
            self.cb_model.blockSignals(False)
            self.lbl_hint.setText(f"{len(ids)} modelo(s) encontrado(s).")
        except httpx.HTTPError as e:
            QMessageBox.warning(
                self, "Buscar modelos",
                f"Não foi possível consultar o endpoint:\n{e}")
        except Exception as e:
            QMessageBox.warning(
                self, "Buscar modelos",
                f"Erro ao buscar modelos:\n{e}")
        finally:
            self.btn_discover.setEnabled(True)
            self.btn_discover.setText("Buscar modelos")

    # ---------- Voz ----------
    def _tab_voice(self):
        v = self.cfg["voice"]
        self.ed_voice = QLineEdit(v.get("voice", "pt-BR-FranciscaNeural"))
        self.ed_rate = QLineEdit(v.get("rate", "+0%"))
        self.ed_vol = QLineEdit(v.get("volume", "+0%"))

        form = QFormLayout()
        form.addRow("Voz (edge-tts)", self.ed_voice)
        form.addRow("Taxa", self.ed_rate)
        form.addRow("Volume", self.ed_vol)

        box = QGroupBox("Voz")
        box.setLayout(form)
        w = QWidget()
        w.setLayout(QVBoxLayout())
        w.layout().addWidget(box)
        return w

    # ---------- Locução & Áudio ----------
    def _tab_locucao(self):
        loc = self.cfg.get("locucao", {})
        audio = self.cfg["audio"]

        self.ch_intro = self._check(loc.get("intro_enabled", True))
        self.ch_outro = self._check(loc.get("outro_enabled", True))
        self.ch_mid = self._check(loc.get("mid_enabled", True))
        self.sp_mid_chance = QSpinBox()
        self.sp_mid_chance.setRange(0, 100)
        self.sp_mid_chance.setSuffix(" %")
        self.sp_mid_chance.setValue(int(loc.get("mid_chance", 0.4) * 100))
        self.sp_mid_min = QSpinBox()
        self.sp_mid_min.setRange(10, 3600)
        self.sp_mid_min.setSuffix(" s")
        self.sp_mid_min.setValue(int(loc.get("mid_min_sec", 60)))

        self.sp_max_intro = self._dur_spin(loc.get("max_dur_intro_sec", 8))
        self.sp_max_outro = self._dur_spin(loc.get("max_dur_outro_sec", 8))
        self.sp_max_mid = self._dur_spin(loc.get("max_dur_mid_sec", 5))

        self.sp_duck = QDoubleSpinBox()
        self.sp_duck.setRange(-60, 0)
        self.sp_duck.setSingleStep(1)
        self.sp_duck.setSuffix(" dB")
        self.sp_duck.setValue(float(audio.get("duck_gain_db", -20)))

        form = QFormLayout()
        form.addRow("Locução de abertura", self.ch_intro)
        form.addRow("Locução de encerramento", self.ch_outro)
        form.addRow("Locução no meio (às vezes)", self.ch_mid)
        form.addRow("Chance de locução no meio", self.sp_mid_chance)
        form.addRow("Duração mínima p/ meio", self.sp_mid_min)
        form.addRow("Máx. duração abertura", self.sp_max_intro)
        form.addRow("Máx. duração encerramento", self.sp_max_outro)
        form.addRow("Máx. duração no meio", self.sp_max_mid)
        form.addRow("Duck gain", self.sp_duck)

        box = QGroupBox("Locução & Áudio")
        box.setLayout(form)
        w = QWidget()
        w.setLayout(QVBoxLayout())
        w.layout().addWidget(box)
        return w

    def _dur_spin(self, value):
        sp = QSpinBox()
        sp.setRange(1, 60)
        sp.setSuffix(" s")
        sp.setValue(int(value))
        return sp

    # ---------- Player ----------
    def _tab_player(self):
        p = self.cfg["player"]
        self.ch_auto_next = self._check(p.get("auto_next", True))
        self.ch_loop = self._check(p.get("loop", True))
        self.sp_prefetch = QSpinBox()
        self.sp_prefetch.setRange(1, 5)
        self.sp_prefetch.setValue(int(p.get("prefetch", 2)))
        self.sp_vol = QSpinBox()
        self.sp_vol.setRange(0, 100)
        self.sp_vol.setSuffix(" %")
        self.sp_vol.setValue(int(p.get("volume", 0.8) * 100))

        form = QFormLayout()
        form.addRow("Avançar automaticamente", self.ch_auto_next)
        form.addRow("Loop na fila", self.ch_loop)
        form.addRow("Faixas preparadas com antecedência", self.sp_prefetch)
        form.addRow("Volume inicial", self.sp_vol)

        box = QGroupBox("Player")
        box.setLayout(form)
        w = QWidget()
        w.setLayout(QVBoxLayout())
        w.layout().addWidget(box)
        return w

    def _check(self, on):
        cb = QCheckBox()
        cb.setChecked(bool(on))
        return cb

    # ---------- coletar ----------
    def apply(self):
        b = self.cfg["brain"]
        api = b.setdefault("api", {})
        b["mode"] = self.cb_mode.currentText()
        b["persona"] = self.ed_persona.toPlainText()
        b["temperature"] = self.sp_temp.value()
        api["base_url"] = self.ed_base_url.text().strip().rstrip("/")
        api["model"] = self.cb_model.currentText().strip()
        api["fallback_model"] = self.ed_fallback.text().strip()
        api["key_cooldown_sec"] = self.sp_cooldown.value()
        api["timeout_sec"] = self.sp_timeout.value()
        api["api_timeout_sec"] = self.sp_api_timeout.value()
        api["keys"] = [k.strip() for k in self.ed_keys.toPlainText().splitlines()
                       if k.strip()]

        v = self.cfg["voice"]
        v["voice"] = self.ed_voice.text()
        v["rate"] = self.ed_rate.text()
        v["volume"] = self.ed_vol.text()

        loc = self.cfg.setdefault("locucao", {})
        loc["intro_enabled"] = self.ch_intro.isChecked()
        loc["outro_enabled"] = self.ch_outro.isChecked()
        loc["mid_enabled"] = self.ch_mid.isChecked()
        loc["mid_chance"] = self.sp_mid_chance.value() / 100.0
        loc["mid_min_sec"] = self.sp_mid_min.value()
        loc["max_dur_intro_sec"] = self.sp_max_intro.value()
        loc["max_dur_outro_sec"] = self.sp_max_outro.value()
        loc["max_dur_mid_sec"] = self.sp_max_mid.value()

        audio = self.cfg["audio"]
        audio["duck_gain_db"] = self.sp_duck.value()

        p = self.cfg["player"]
        p["auto_next"] = self.ch_auto_next.isChecked()
        p["loop"] = self.ch_loop.isChecked()
        p["prefetch"] = self.sp_prefetch.value()
        p["volume"] = self.sp_vol.value() / 100.0
