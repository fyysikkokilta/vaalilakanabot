# Vaalilakanabot

Telegram-botti, joka vaalien aikaan ylläpitää listausta ehdolle asettuneista henkilöistä ja ilmoittaa uusista postauksista killan Discourse-pohjaisella keskustelufoorumilla [Φrumilla](https://fiirumi.fyysikkokilta.fi).

## Ominaisuudet

- Kiltalaiset voivat hakea sekä vaaleilla valittaviin että ei-vaaleilla valittaviin virkoihin.
- **Admin-hyväksyntä**: Hakemukset vaaleilla valittaviin virkoihin (hallitus ja valittavat toimihenkilöt) vaativat admin-hyväksynnän ennen lisäämistä vaalilakanaan.
- Ilmoittaa chatteissa, joihin botti on lisätty, aina kun fiirumille on tullut uusi postaus.
- Botin admin-käyttäjä voi ylläpitää sähköistä vaalilakanaa.
- Jauhistelu

## CI/CD Pipeline

This project uses GitHub Actions for continuous integration and deployment:

- **Automatic builds**: Docker images are automatically built and pushed to GitHub Container Registry on every push to main/master branch
- **Image tags**: Images are tagged with branch name, commit SHA, and semantic version tags
- **Registry**: Images are available at `ghcr.io/fyysikkokilta/vaalilakanabot`

### Development vs Production

- **Development**: Use `docker-compose up` (uses local build via override file)
- **Production**: Use `docker-compose -f docker-compose.prod.yml up` (uses pre-built image)

## Käyttöönotto

- asenna `python-telegram-bot`-kirjasto (versio >=21) ja muut tarvittavat kirjastot.
- lisää Telegram-bot Bot Father -botilla ja ota botin token talteen.
- Luo Discourse api-avain bottia varten.
- Luo admin Telegram-ryhmä ja ota sen id talteen esimerkiksi botilla `@RawDataBot`.
- Luo vaalilakana Fiirumille.
  - Viestissä, jossa vaalilakana sijaitsee ei saa olla muuta tekstiä kuin itse vaalilakana.
  - Jaoksien nimet tulee olla ISOLLA kirjoitettuna ja rivi saa sisältää vain suomenkielisen ja englanninkielisen käännöksen /-merkillä jaettuna.
  - Roolirivit tulee olla muodossa `{suomenkielinen nimi} / {englanninkielinen nimi} ({valittavien määrä}) {haun deadline (muodossa xx.yy.}`
    - Kaikki muut paitsi suomenkielinen nimi ovat vapaaehtoisia, mutta järjestyksen tulee olla juuri tämä.
- Luo `bot.env` esimerkkitiedoston `bot.env.example` mukaisesti.
- `$ python vaalilakanabot.py`
- lisää botti relevantteihin keskusteluryhmiin.

## Running the bot with Docker

- Create a Telegram bot and save the bot token.
- Create Discourse api keys to be used by the bot.
- Create an admin Telegram group and get the id of the group using, for example, `@RawDataBot`.
- Create the vaalilakana for Fiirumi.
  - The message containing the vaalilakana must not have any text other than the vaalilakana itself.
  - Division names must be written in ALL CAPS, and each line should contain only the Finnish and English translations separated by a `/`.
  - Role lines must follow the format:  
    `{Finnish name} / {English name} ({number of positions}) {application deadline (in the format xx.yy.)}`
    - Everything except the Finnish name is optional, but the order must be exactly as specified.
- Create `bot.env` according to the example file `bot.env.example`.
- Make sure the empty vaalilakana is already created when starting the bot so that the local json is populated.

### Docker Deployment Options

**Development (local build):**

```bash
docker-compose up
```

**Production (pre-built image):**

```bash
docker-compose -f docker-compose.prod.yml up
```

**Using the deployment script:**

```bash
./update-deployment.sh
```

## Komennot

Botti tukee seuraavia komentoja:

- `/start` Rekisteröi ryhmän botin tiedotuskanavaksi ja ryhmää saa botilta ilmoituksia.
- `/lakana` Näyttää vaalien ehdokastilanteen (suomeksi).
- `/sheet` Näyttää vaalien ehdokastilanteen (englanniksi).
- `/jauhis` Näyttää vaaliaiheisen kuvan.
- `/jauh` Näyttää vaaliaiheisen kuvan.
- `/jauho` Näyttää vaaliaiheisen kuvan.
- `/lauh` Näyttää vaaliaiheisen kuvan.
- `/mauh` Näyttää vaaliaiheisen kuvan.
- `/hae` Aloittaa hakemuslomakkeen täyttämisen suomeksi.
- `/apply` Aloittaa hakemuslomakkeen täyttämisen englanniksi.
- `/help` Näyttää englanninkielisen ohjeen.
- `/apua` Näyttää suomenkielisen ohjeen.

Admin-chatissa seuraavat komennot ovat käytössä:

- `/remove` Poistaa ehdokkaan lakanasta. (toimii myös ei-vaaleilla valittavaan virkoihin; hakijan voi siis poistaa botin kautta)
- `/add_fiirumi` Lisää ehdokkaan fiirumipostauksen vaalilakanaan.
- `/remove_fiirumi` Poistaa vaalilakanaan lisätyn fiirumipostauksen.
- `/selected` Merkitsee vaalilakanassa ehdokkaan valituksi virkaan. (toimii myös ei-vaaleilla valittavaan virkoihin)
- `/edit_or_add_new_role` Lisää uuden roolin tai muokkaa olevassa olevaa roolia vaalilakanassa.
- `/remove_role` Poistaa roolin vaalilakanasta.
- `/export_data` Luo hakijoiden tiedoista CSV-tiedoston.
- `/pending` Näyttää kaikki odottavat hakemukset, jotka vaativat admin-hyväksynnän.
- `/admin_help` Näyttää admin-komentojen ohjeen.

**Huomio:** Admin-komennot tukevat sekä suomen- että englanninkielisiä jaos- ja roolinimiä. Jos nimiä ei löydy, botti näyttää saatavilla olevat vaihtoehdot.

### Admin-hyväksyntä

Hakemukset vaaleilla valittaviin virkoihin (määritellään `BOARD` ja `ELECTED_OFFICIALS` ympäristömuuttujissa) vaativat admin-hyväksynnän:

1. Kun käyttäjä lähettää hakemuksen vaaleilla valittavaan virkaan, botti lähettää hyväksyntäpyynnön admin-chatin.
2. Admin-chatissa näkyy hakemuksen tiedot ja kaksi painiketta: "✅ Approve" ja "❌ Reject".
3. Kun admin hyväksyy hakemuksen:
   - Hakemus lisätään vaalilakanaan
   - Hakijalle lähetetään hyväksyntäilmoitus
   - Kanaville lähetetään tavallinen ilmoitus uudesta nimestä vaalilakanassa
4. Kun admin hylkää hakemuksen:
   - Hakemus poistetaan odottavien listalta
   - Hakijalle lähetetään hylkäysilmoitus
5. Käyttäjä ei voi lähettää uutta hakemusta samaan virkaan niin kauan kun edellinen hakemus odottaa käsittelyä.

## Lisätietoa

Lisää telegram-boteista voi lukea esimerkiksi [Kvantti I/19 s.22-25](https://kvantti.ayy.fi/blog/wp-content/uploads/2019/03/kvantti-19-1-nettiin.pdf).

Botin tekivät [Einari Tuukkanen](https://github.com/EinariTuukkanen) ja Uula Ollila.
