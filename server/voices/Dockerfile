# ════════════════════════════════════════════════════════════════════════
#  DEWIAR VOICES — живые голоса персонажей (Qwen3-TTS + ESpeech) для всех приложений
#  Путь на сервере: /app/src/vllm/tts/Dockerfile
#  Собирает и запускает панель: /vllm/voices.php → «Установить» (lib/ttsctl.php).
#  Модели держатся в памяти видеокарты → первая фраза звучит через доли секунды.
#
#  Какой torch ставить, задаёт TORCH_INDEX: …/whl/cu128 — видеокарта (RTX 3090 и новее), …/whl/cpu — процессор
#  (на процессоре голос будет очень медленным — только для проверки).
# ════════════════════════════════════════════════════════════════════════
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HUB_CACHE=/models

# ffmpeg — образцы голосов из mp3/m4a/ogg, темп речи, mp3 в ответе; sox — его просит qwen-tts
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg sox libsox-fmt-all curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG TORCH_INDEX=https://download.pytorch.org/whl/cu128
RUN pip install torch torchaudio --index-url ${TORCH_INDEX}

# Версия qwen-tts зафиксирована: обновление — осознанно, сменой здесь.
ARG QWEN_TTS_VERSION=0.1.1
RUN pip install "qwen-tts==${QWEN_TTS_VERSION}" numpy soundfile

# Быстрый Qwen (faster-qwen3-tts, CUDA graphs) и русский голос ESpeech (F5-TTS) с ударениями RUAccent — отдельным
# слоем: torch и qwen-tts выше берутся из кэша. torch и torchaudio не меняются (constraints); torchcodec не нужен —
# звук читаем сами, а его сборка под другой torch ломает импорт.
ARG FASTER_QWEN_VERSION=0.3.2
ARG F5_VERSION=1.1.22
ARG RUACCENT_VERSION=1.5.8.3
RUN pip freeze | grep -iE '^(torch|torchaudio)==' > /tmp/keep.txt \
    && pip install -c /tmp/keep.txt "faster-qwen3-tts==${FASTER_QWEN_VERSION}" "f5-tts==${F5_VERSION}" "ruaccent==${RUACCENT_VERSION}" \
    && (pip uninstall -y torchcodec || true)

# Словари и модели ударений — в образ: не качаются при каждом запуске
RUN python -c "from ruaccent import RUAccent; a = RUAccent(); a.load(omograph_model_size='turbo3.1', use_dictionary=True, workdir='/opt/ruaccent'); print(a.process_all('Привет, я голос Девиара.'))"

# CosyVoice3 — проба (19.11): ставится, только если в панели выбран движок «CosyVoice3» (COSY=1), в своё окружение
# /opt/cosy — его зависимости не смешиваются со службой. Убрать: выбрать ESpeech и «Обновить службу» — образ соберётся без него.
ARG COSY=0
ARG COSY_REF=main
LABEL dewiar.cosy=${COSY}
RUN if [ "$COSY" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends git build-essential && rm -rf /var/lib/apt/lists/* \
      && python -m venv /opt/cosy \
      && git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git /opt/cosy/src \
      && git -C /opt/cosy/src checkout "${COSY_REF}" && git -C /opt/cosy/src submodule update --init --recursive \
      && /opt/cosy/bin/pip install -r /opt/cosy/src/requirements.txt huggingface_hub numpy ; \
    fi

WORKDIR /opt/voices
COPY *.py ./

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["python", "app.py"]
