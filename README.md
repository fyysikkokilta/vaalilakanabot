# Vaalilakanabot

Telegram-botti, joka vaalien aikaan ylläpitää listausta ehdolle asettuneista henkilöistä ja ilmoittaa uusista postauksista killan Discourse-pohjaisella keskustelufoorumilla [Φrumilla](https://fiirumi.fyysikkokilta.fi). 

## Ominaisuudet
- Ilmoittaa chatteissa, joihin botti on lisätty, aina kun fiirumille on tullut uusi postaus 
- Botin admin-käyttäjä voi ylläpitää sähköistä vaalilakanaa
- Jauhistelu

## Käyttöönotto
- asenna `python-telegram-bot`-kirjasto (versio >=12) ja muut tarvittavat kirjastot
- lisää Bot Fatherilta saatava `VAALILAKANABOT_TOKEN` ympäristönmuuttujaksi käyttöjärjestelmään.
- täydennä ADMIN_CHAT_ID koodiin (halutun ryhmän id:n saa esimerkiksi lisäämällä botin `@RawDataBot` haluttuun ryhmään)
- Päivitä TOPIC_LIST_URL ja QUESTION_LIST_URL -muuttujat koodiin. Katso [Discoursen dokumentaatio](https://docs.discourse.org/#tag/Categories/paths/~1c~1{id}.json/get) oikeanlaisen URL:n asettamiseksi.
- `$ python vaalilakanabot.py` 
- lisää botti relevantteihin keskusteluryhmiin

## Running the bot with Docker
- create Discourse api keys to be used by the bot
- create `bot.env` according to the example file `bot.env.example`
- make sure the empty vaalilakana is already created when starting the bot so that the local json is populated
- start the bot using provided `update-deployment.sh` script

## Komennot
Botti tukee seuraavia komentoja:
- `/start` Rekisteröi ryhmän botin tiedotuskanavaksi ja ryhmää saa botilta ilmoituksia.
- `/hae` Aloittaa hakemuslomakkeen täyttämisen.
- `/jauhis` Näytää vaaliaiheisen kuvan.
- `/jauh` Näytää vaaliaiheisen kuvan.
- `/jauho` Näytää vaaliaiheisen kuvan.
- `/lauh` Näytää vaaliaiheisen kuvan.
- `/mauh` Näytää vaaliaiheisen kuvan.
- `/lakana` Näytää vaalien ehdokastilanteen.

Admin-chatissa seuraavat komennot ovat käytössä:
- `/lisaa` Lisää ehdokkaan vaalilakanaan.
- `/lisaa_fiirumi` Lisää ehdokkaan fiirumipostauksen vaalilakanaan.
- `/poista` Poistaa ehdokkaan lakanasta. (toimii myös ei-vaaleilla valittavaan virkoihin; hakijan voi siis poistaa botin kautta)
- `/valittu` Merkitsee vaalilakanassa ehdokkaan valituksi virkaan. (toimii myös ei-vaaleilla valittavaan virkoihin)
- `/tiedota` Julkaisee uuden merkinnän vaalilakanassa.

## Lisätietoa
Lisää telegram-boteista voi lukea esimerkiksi [Kvantti I/19 s.22-25](https://kvantti.ayy.fi/blog/wp-content/uploads/2019/03/kvantti-19-1-nettiin.pdf). 

Botin tekivät [Einari Tuukkanen](https://github.com/EinariTuukkanen) ja Uula Ollila.
