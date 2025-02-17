# Vaalilakanabot

Telegram-botti, joka vaalien aikaan ylläpitää listausta ehdolle asettuneista henkilöistä ja ilmoittaa uusista postauksista killan Discourse-pohjaisella keskustelufoorumilla [Φrumilla](https://fiirumi.fyysikkokilta.fi). 

## Ominaisuudet
- Kiltalaiset voivat hakea sekä vaaleilla valittaviin että ei-vaaleilla valittaviin virkoihin.
- Ilmoittaa chatteissa, joihin botti on lisätty, aina kun fiirumille on tullut uusi postaus.
- Botin admin-käyttäjä voi ylläpitää sähköistä vaalilakanaa.
- Jauhistelu

## Käyttöönotto
- asenna `python-telegram-bot`-kirjasto (versio >=21) ja muut tarvittavat kirjastot.
- lisää Bot Fatherilta saatava `VAALILAKANABOT_TOKEN` ympäristönmuuttujaksi käyttöjärjestelmään.
- täydennä ADMIN_CHAT_ID koodiin. (halutun ryhmän id:n saa esimerkiksi lisäämällä botin `@RawDataBot` haluttuun ryhmään)
- Päivitä TOPIC_LIST_URL ja QUESTION_LIST_URL -muuttujat koodiin. Katso [Discoursen dokumentaatio](https://docs.discourse.org/#tag/Categories/paths/~1c~1{id}.json/get) oikeanlaisen URL:n asettamiseksi.
- `$ python vaalilakanabot.py` 
- lisää botti relevantteihin keskusteluryhmiin.

## Running the bot with Docker
- create Discourse api keys to be used by the bot.
- create `bot.env` according to the example file `bot.env.example`.
- make sure the empty vaalilakana is already created when starting the bot so that the local json is populated.
- start the bot using provided `update-deployment.sh` script.

## Komennot
Botti tukee seuraavia komentoja:
- `/start` Rekisteröi ryhmän botin tiedotuskanavaksi ja ryhmää saa botilta ilmoituksia.
- `/lakana` Näyttää vaalien ehdokastilanteen.
- `/jauhis` Näyttää vaaliaiheisen kuvan.
- `/jauh` Näyttää vaaliaiheisen kuvan.
- `/jauho` Näyttää vaaliaiheisen kuvan.
- `/lauh` Näyttää vaaliaiheisen kuvan.
- `/mauh` Näyttää vaaliaiheisen kuvan.
- `/hae` Aloittaa hakemuslomakkeen täyttämisen.

Admin-chatissa seuraavat komennot ovat käytössä:
- `/poista` Poistaa ehdokkaan lakanasta. (toimii myös ei-vaaleilla valittavaan virkoihin; hakijan voi siis poistaa botin kautta)
- `/lisaa_fiirumi` Lisää ehdokkaan fiirumipostauksen vaalilakanaan.
- `/poista_fiirumi` Poistaa vaalilakanaan lisätyn fiirumipostauksen.
- `/valittu` Merkitsee vaalilakanassa ehdokkaan valituksi virkaan. (toimii myös ei-vaaleilla valittavaan virkoihin)
- `/muokkaa_roolia` Lisää uuden roolin tai muokkaa olevassa olevaa roolia vaalilakanassa.
- `/poista_rooli` Poistaa roolin vaalilakanasta.
- `/vie_tiedot` Luo hakijoiden tiedoista CSV-tiedoston.

## Lisätietoa
Lisää telegram-boteista voi lukea esimerkiksi [Kvantti I/19 s.22-25](https://kvantti.ayy.fi/blog/wp-content/uploads/2019/03/kvantti-19-1-nettiin.pdf). 

Botin tekivät [Einari Tuukkanen](https://github.com/EinariTuukkanen) ja Uula Ollila.
