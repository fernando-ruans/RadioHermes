"""Cérebro do locutor: LLM via QUALQUER endpoint OpenAI-compatível, com
ROTAÇÃO de múltiplas chaves API e cooldown automático (BYOK).

Funciona com qualquer provedor OpenAI-like:
  Gemini (via endpoint openai), OpenAI, Groq, Ollama, LM Studio,
  vLLM, llama.cpp, proxies locais, etc. Basta apontar base_url + model.

- Chaves em round-robin a partir da última usada com sucesso.
- Chave que falha (429/timeout/erro) entra em cooldown e a próxima assume.
- Provedores sem auth (Ollama/LM Studio local) podem usar chave dummy
  (ex: "local") — o header Bearer é ignorado por eles.
- Se tudo falhar, degrada para o template local (o app nunca trava).

Contextos de locução (kind):
  intro — ANTES da música tocar (anuncia a próxima)
  mid   — NO MEIO da música (com ducking, sem interromper)
  outro — DEPOIS da música tocar (encerra / gancho pra próxima)
"""
import asyncio
import httpx
import random
import time


class Brain:
    def __init__(self, cfg):
        b = cfg["brain"]
        self.mode = b.get("mode", "template")
        self.persona = b.get("persona", "Você é o locutor da rádio.")
        self.temperature = b.get("temperature", 0.9)
        api = b.get("api", {})
        self.base_url = api.get("base_url", "").rstrip("/")
        keys = api.get("keys") or []
        single = api.get("api_key", "")
        if single:
            keys = [single] + keys
        self.keys = [k.strip() for k in keys if k and k.strip()]
        self.model = api.get("model", "")
        self.fallback_model = api.get("fallback_model", "")
        self.key_cooldown = float(api.get("key_cooldown_sec", 60))
        self.timeout = float(api.get("timeout_sec", 8))
        self.api_timeout = float(api.get("api_timeout_sec", 8))
        self._cur = 0
        self._cooldown_until = {}

    # ---------- rotação ----------
    def _healthy_key(self):
        n = len(self.keys)
        if n == 0:
            return None
        now = time.monotonic()
        self._cooldown_until = {i: t for i, t in self._cooldown_until.items()
                                if t > now}
        for off in range(n):
            idx = (self._cur + off) % n
            if idx not in self._cooldown_until:
                return idx, self.keys[idx]
        return None

    def _block_key(self, idx):
        self._cooldown_until[idx] = time.monotonic() + self.key_cooldown
        self._cur = (idx + 1) % len(self.keys)

    # ---------- API ----------
    async def announce(self, ctx):
        if self.mode == "api" and self.base_url:
            try:
                return await asyncio.wait_for(
                    self._api(ctx), timeout=self.api_timeout)
            except Exception as e:
                print(f"[brain] LLM falhou em todas as chaves ({e}); "
                      f"usando template local.")
        return self._template(ctx)

    def _style_instruction(self):
        styles = [
            "tom animado e descontraído, como um locutor de rádio matinal",
            "tom caloroso e acolhedor, como quem fala com um amigo",
            "tom misterioso e sedutor, tipo locução de rádio noturna",
            "tom enérgico e empolgado, contagiando o ouvinte",
            "tom poético e suave, com leveza",
        ]
        return random.choice(styles)

    # ---------- comportamentos rotativos (imprevisibilidade natural) ----------
    # Cada comportamento: (chave, peso). Sorteado a cada locução.
    _BEHAVIORS = {
        "intro": [
            ("musica", 3),   # foca em anunciar a música
            ("horario", 2),  # marca a hora + anuncia
            ("ouvinte", 1),  # fala com o ouvinte + anuncia
            ("clima", 1),    # vibe/sensação do dia + introduz
        ],
        "mid": [
            ("comenta", 3),  # comentário sobre a música tocando
            ("horario", 2),  # momento/hora
            ("audiencia", 1),# interage direto com o ouvinte
        ],
        "outro": [
            ("encerra", 3),  # encerra comentando a música
            ("horario", 2),  # hora + encerra
            ("gancho", 1),   # comenta + gancho pra próxima
        ],
    }

    def _pick_behavior(self, kind):
        pool = self._BEHAVIORS.get(kind, self._BEHAVIORS["mid"])
        keys = [k for k, w in pool for _ in range(w)]
        return random.choice(keys)

    def _style_instruction(self):
        styles = [
            "tom animado e descontraído, como um locutor de rádio matinal",
            "tom caloroso e acolhedor, como quem fala com um amigo",
            "tom misterioso e sedutor, tipo locução de rádio noturna",
            "tom enérgico e empolgado, contagiando o ouvinte",
            "tom poético e suave, com leveza",
        ]
        return random.choice(styles)

    def _time_line(self, ctx):
        """Frase de contexto temporal natural. Sempre coerente com a hora real."""
        hour = ctx.get("hour")
        minute = ctx.get("minute")
        period = ctx.get("period", "")
        if hour is None:
            return "Ao longo do dia"
        if minute in ("00", "0", ""):
            return f"Agora são {hour}h {period}"
        return f"Agora são {hour}:{minute} {period}"

    def _dur_line(self, ctx):
        secs = ctx.get("max_dur_sec")
        if secs:
            words = max(8, int(secs * 2.6))
            return (f"Sua fala deve durar APROXIMADAMENTE {secs} segundos "
                    f"(cerca de {words} palavras) no máximo.")
        return "Fale frases curtas e naturais (máx 35 palavras)."

    def _build_prompt(self, ctx):
        kind = ctx.get("kind", "mid")
        behavior = ctx.get("behavior") or self._pick_behavior(kind)
        style = self._style_instruction()
        title = ctx.get("title", "")
        nxt = ctx.get("next_title", "")
        dur = self._dur_line(ctx)
        context = f"{self._time_line(ctx)} na Rádio Hermes."

        def block(tarefa, extra=""):
            s = f"--- contexto ---\n{context}\n"
            if title:
                s += f"A música em foco: '{title}'.\n"
            if nxt:
                s += f"Na sequência, toca: '{nxt}'.\n"
            s += f"\n--- tarefa ---\n{tarefa}\n"
            s += f"\nRegra de tamanho: {dur}\n{extra}"
            return s

        if kind == "intro":
            return block(
                f"Faça uma abertura de 1-2 frases com {style}, convidando o ouvinte a curtir. "
                f"Sinta-se livre para não repetir sempre o mesmo formato.",
                "Dica: só mencione a música se encaixar bem; o que importa é abertura natural.",
            )
        if kind == "outro":
            return block(
                f"Faça um encerramento de 1-2 frases com {style}, comentando o que passou. "
                f"{('Jogue um gancho para o que vem a seguir: ' + nxt + '.') if nxt else ''}"
                f"Sinta-se livre para variar o formato.",
            )
        return block(
            f"Faça um comentário breve de 1 frase com {style} sobre o momento da rádio, "
            f"criando clima, sem spoilers. Pode ser sobre a música, a hora ou o ouvinte.",
        )

    async def _try_one(self, idx, key, ctx, model):
        system = (self.persona +
                  "\n\nPersonalidade: você conhece o horário, o dia da semana e o período do dia. "
                  "Adapte naturalmente o tom: manhã = enérgico, tarde = relaxado, noite = intimista, "
                  "madrugada = calmo. Varie o que você fala: às vezes foque na música, às vezes no "
                  "horário, às vezes no ouvinte, às vezes no clima. Seja imprevisível mas agradável. "
                  "NUNCA contradiga o horário real (ex: não fale 'madrugada' às 14h).")
        system += ("\n\nRegras obrigatórias: fale em português do Brasil, tom de locutor de rádio FM. "
                   "MÁXIMO 1 a 2 frases curtas. NÃO use emojis, aspas, asteriscos, crases, "
                   "markdown, listas nem qualquer marcador. Responda APENAS com a fala do locutor, "
                   "nada mais — sem explicações, sem rodeios.")
        system += ("\n\nImportante: seu texto é convertido em voz para o rádio. "
                   "Ele DEVE caber em poucos segundos de fala. Se for longo, encurte para o essencial.")
        user = self._build_prompt(ctx)
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.post(
                self.base_url + "/chat/completions",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={"model": model, "temperature": self.temperature,
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}]},
            )
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return self._clean(
                r.json()["choices"][0]["message"]["content"].strip())

    @staticmethod
    def _clean(text):
        """Remove marcadores comuns que modelos locais emitem (markdown,
        crases, asteriscos, aspas extras) e encurta para 1-2 frases."""
        import re
        # remove blocos de código
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        # remove crases, asteriscos, cifrões, # e hífens de lista
        text = re.sub(r"[`*#_~]", "", text)
        text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.MULTILINE)
        # remove aspas em volta de toda a fala
        text = text.strip().strip('"\'\u201c\u201d')
        text = " ".join(text.split())
        # limita a 2 frases (termina em . ? !) para garantir concisão
        sents = re.split(r"(?<=[.?!])\s+", text)
        if len(sents) > 2:
            text = " ".join(sents[:2]).strip()
        return text

    async def _api(self, ctx):
        # Sem chaves? (Ollama/LM Studio local) usa uma dummy — o header
        # Bearer é ignorado por provedores sem auth.
        if not self.keys:
            self.keys = ["local"]
        n = len(self.keys)
        tried = set()
        while len(tried) < n:
            k = self._healthy_key()
            if k is None:
                break
            idx, key = k
            tried.add(idx)
            try:
                return await self._try_one(idx, key, ctx, self.model)
            except Exception:
                self._block_key(idx)
        if not self.fallback_model:
            raise RuntimeError("todas as chaves exauriram (sem fallback)")
        tried2 = set()
        while len(tried2) < n:
            k = self._healthy_key()
            if k is None:
                break
            idx, key = k
            tried2.add(idx)
            try:
                return await self._try_one(idx, key, ctx, self.fallback_model)
            except Exception:
                self._block_key(idx)
        raise RuntimeError("todas as chaves exauriram")

    # ---------- template local ----------
    def _template(self, ctx):
        kind = ctx.get("kind", "mid")
        behavior = ctx.get("behavior") or self._pick_behavior(kind)
        title = ctx.get("title", "essa música")
        nxt = ctx.get("next_title", "")
        hour = ctx.get("hour")
        period = ctx.get("period", "")
        if hour is not None and ctx.get("minute") in ("00", "0", ""):
            hora = f"{hour}h {period}".strip()
        elif hour is not None:
            hora = f"{hour}:{ctx.get('minute')} {period}".strip()
        else:
            hora = "agora"

        if behavior == "horario":
            base = [
                f"Marquei aqui: {hora} na Rádio Hermes. Hora de relaxar e curtir o som.",
                f"Rádio Hermes, {hora} em ponto. Perfeito pra esvaziar a cabeça com boa música.",
                f"São {hora} e a Rádio Hermes continua com o melhor da música.",
            ]
            if kind == "intro" and title != "essa música":
                base.append(f"São {hora} e o que vem por aí é especial: {title}.")
            return random.choice(base)

        if kind == "intro":
            frases = [
                f"Agora sim! Chegou a vez de {title}. Senta, relaxa e deixa o som falar por si.",
                f"Direto do coração da Rádio Hermes pra você: {title}. Aproveita!",
                f"O que vem a seguir é coisa fina: {title}. Fica com a gente!",
            ]
            if period == "tarde":
                frases.append(f"Tarde boa pra quem tá com a gente! Aí vem {title}.")
            elif period == "manhã":
                frases.append(f"Bom dia de som! Pra começar bem, {title}.")
        elif kind == "outro":
            frases = [
                f"E foi {title} na Rádio Hermes. Que viagem boa, hein?",
                f"{title} acabou de passar por aqui. Se você curtiu, o próximo tá chegando.",
            ]
            if nxt:
                frases.append(f"{title} ficou pra trás. Na sequência, {nxt}.")
            if period == "noite":
                frases.append(f"{title} já era! A noite continua boa na Rádio Hermes.")
        else:
            frases = [
                f"{title} tocando agora na Rádio Hermes. Aproveita o momento!",
                f"Nesse clima de {title}, a Rádio Hermes fica ainda melhor.",
                f"{title} no ar! Só deixar o som envolver.",
            ]
        return random.choice(frases)
