# Vaalilakanabot

Telegram-botti, joka vaalien aikaan ylläpitää listausta ehdolle asettuneista henkilöistä ja ilmoittaa uusista postauksista killan keskustelufoorumilla [Φrumilla](https://fiirumi.fyysikkokilta.fi). 

## Ominaisuudet
- Ilmoittaa chatteissa, joihin botti on lisätty, aina kun fiirumille on tullut uusi postaus 
- Botin admin-käyttäjä voi ylläpitää sähköistä vaalilakaa
- Jauhistelu

## Käyttöönotto
- asenna `python-telegram-bot`-kirjasto (versio >=12) ja muut tarvittavat kirjastot
- lisää Bot Fatherilta saatava `VAALILAKANABOT_TOKEN` ympäristönmuuttujaksi käyttöjärjestelmään.
- täydennä ADMIN_CHAT_ID koodiin (halutun ryhmän id:n saa esimerkiksi lisäämällä botin `@RawDataBot` haluttuun ryhmään)
- Päivitä TOPIC_LIST_URL ja QUESTION_LIST_URL -muuttujat koodiin
- `$ python vaalilakanabot2019.py` 
- lisää botti relevantteihin keskusteluryhmiin

Botti tukee seuraavia komentoja:
- `/start` Rekisteröi ryhmän botin tiedotuskanavaksi ja ryhmää saa botilta ilmoituksia.
- `/jauhis` Näytää vaaliaiheisen kuvan.
- `/lakana` Näytää vaalien ehdokastilanteen.

Admin-chatissa seuraavat komennot ovat käytössä:
- `/lisaa` Lisää ehdokkaan vaalilakanaan.
- `/lisaa_fiirumi` Lisää ehdokkaan fiirumipostauksen vaalilakanaan.
- `/poista` Poistaa ehdokkaan lakanasta.
- `/valittu` Merkitsee vaalilakanassa ehdokkaan valituksi virkaan.
- `/tiedota` Julkaisee uuden merkinnän vaalilakanassa.


Lisää telegram-boteista voi lukea esimerkiksi [Kvantti I/19 s.22-25](https://kvantti.ayy.fi/blog/wp-content/uploads/2019/03/kvantti-19-1-nettiin.pdf). 

Botin tekivät Einari Tuukkanen ja Uula Ollila.
