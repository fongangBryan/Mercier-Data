# Même version de Python que sur le poste de développement (3.14) :
# les versions figées de requirements.txt l'exigent.
FROM python:3.14-slim

# Un JDK, puisque le moteur tarifaire est en Java et qu'il faut le
# compiler (javac) pendant la construction.
RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-21-jdk-headless \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Les dépendances d'abord : cette couche reste en cache tant que
# requirements.txt ne change pas, ce qui accélère les reconstructions.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN javac java/Tarif.java

# La base et la zone brute vivent sur un volume, hors du conteneur.
ENV MERCIER_ENV=production \
    MERCIER_ENTREPOT=/donnees/entrepot.db \
    MERCIER_ZONE_BRUTE=/donnees/zone_brute \
    PYTHONUNBUFFERED=1
VOLUME ["/donnees"]

# On ne tourne pas en root dans le conteneur.
RUN useradd --create-home mercier && mkdir -p /donnees \
 && chown -R mercier /donnees /app
USER mercier

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/sante')"

CMD ["python", "-m", "uvicorn", "mercier.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
