packer = 7z
pack = $(packer) a -mx=9
arcx = .7z
docs = COPYING Changelog README.md wishlist.json
basename = wishcalc
zipname = $(basename).zip
arcname = $(basename)$(arcx)
srcarcname = $(basename)-src$(arcx)
srcs = __main__.py wishcalc.py wcconfig.py wcdata.py gtktools.py wishcalc*.ui wishcalc*.svg nmicon*.svg
version = $(shell python3 -c 'from wishcalc import VERSION; print(VERSION)')
title_version = $(shell python3 -c 'from $(srcversion) import TITLE_VERSION; print(TITLE_VERSION)')
backupdir = ~/shareddocs/pgm/python/

app:
	$(pack) -tzip $(zipname) $(srcs)
	@echo '#!/usr/bin/env python3' >$(basename)
	@cat $(zipname) >>$(basename)
	rm $(zipname)
	chmod 755 $(basename)

archive:
	$(pack) $(srcarcname) *.py *. Makefile *.geany *.ui *.svg $(docs)
distrib:
	make app
	$(eval distname = $(basename)-$(version)$(arcx))
	$(pack) $(distname) $(basename) $(docs)
	mv $(distname) ~/downloads/
backup:
	make archive
	mv $(srcarcname) $(backupdir)
update:
	$(packer) x -y $(backupdir)$(srcarcname)
commit:
	git commit -a -uno -m "$(version)"
docview:
	$(eval docname = README.htm)
	@echo "<html><head><meta charset="utf-8"><title>$(title_version) README</title></head><body>" >$(docname)
	markdown_py README.md >>$(docname)
	@echo "</body></html>" >>$(docname)
	x-www-browser $(docname)
	#rm $(docname)

