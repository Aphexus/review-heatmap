# -*- coding: utf-8 -*-

"""
This file is part of the Review Heatmap add-on for Anki

Copyright: (c) 2016-2018 Glutanimate <https://glutanimate.com/>
License: GNU AGPLv3 <https://www.gnu.org/licenses/agpl.html>
"""

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from anki.hooks import wrap


from aqt.qt import *
from aqt.overview import Overview
from aqt.deckbrowser import DeckBrowser
from aqt.stats import DeckStats
from anki.stats import CollectionStats
from anki.hooks import addHook, remHook

from .libaddon.platform import ANKI21

from .config import config
from .heatmap import HeatmapCreator

# Deck Browser (Main view)
######################################################################

def deckbrowserRenderStats(self, _old):
    """Add heatmap to _renderStats() return"""
    # self is deckbrowser
    ret = _old(self)
    hmap = HeatmapCreator(config, whole=True)
    html = ret + hmap.generate(view="deckbrowser")
    return html

# Overview (Deck view)
######################################################################

ov_body = """
<center>
<h3>%(deck)s</h3>
%(shareLink)s
%(desc)s
%(table)s
%(stats)s
</center>
<script>$(function () { $("#study").focus(); });</script>
"""

def overviewRenderPage(self):
    """Replace original _renderPage()
    We use this instead of _table() in order to stay compatible
    with other add-ons
    (add-ons like more overview stats overwrite _table())
    TODO: consider using onProfileLoaded instead
    """
    # self is overview
    deck = self.mw.col.decks.current()
    self.sid = deck.get("sharedFrom")
    if self.sid:
        self.sidVer = deck.get("ver", None)
        shareLink = '<a class=smallLink href="review">Reviews and Updates</a>'
    else:
        shareLink = ""

    hmap = HeatmapCreator(config, whole=False)

    if not ANKI21:
        self.web.stdHtml(self._body % dict(
            deck=deck['name'],
            shareLink=shareLink,
            desc=self._desc(deck),
            table=self._table(),
            stats=hmap.generate(view="overview")
        ), self.mw.sharedCSS + self._css)
    else:
        self.web.stdHtml(self._body % dict(
            deck=deck['name'],
            shareLink=shareLink,
            desc=self._desc(deck),
            table=self._table(),
            stats=hmap.generate(view="overview")
        ),
            css=["overview.css"],
            js=["jquery.js", "overview.js"])


# CollectionStats (Stats window)
######################################################################

def collectionStatsDueGraph(self, _old):
    """Wraps dueGraph and adds our heatmap to the stats screen"""
    #self is anki.stats.CollectionStats
    # TODO: consider how to handle cusotm limhist/fcst vals
    ret = _old(self)
    if self.type == 0:
        limhist, limfcst = 31, 31
    elif self.type == 1:
        limhist, limfcst = 365, 365
    elif self.type == 2:
        limhist, limfcst = None, None
    hmap = HeatmapCreator(config, whole=self.wholeCollection)
    report = hmap.generate(view="stats", limhist=limhist, limfcst=limfcst)
    return report + ret


def deckStatsInit21(self, mw):
    self.form.web.onBridgeCmd = self._linkHandler
    # refresh heatmap on options change:
    addHook('reset', self.refresh)


def deckStatsInit20(self, mw):
    """Custom stats window that uses AnkiWebView instead of QWebView"""
    # self is aqt.stats.DeckWindow
    QDialog.__init__(self, mw, Qt.Window)
    self.mw = mw
    self.name = "deckStats"
    self.period = 0
    self.form = aqt.forms.stats.Ui_Dialog()
    self.oldPos = None
    self.wholeCollection = False
    self.setMinimumWidth(700)
    f = self.form
    f.setupUi(self)
    #########################################################
    # remove old webview created in form:
    # (TODO: find a less hacky solution)
    f.verticalLayout.removeWidget(f.web)
    f.web.deleteLater()
    f.web = AnkiWebView()  # need to use AnkiWebView for linkhandler to work
    f.web.setLinkHandler(self._linkHandler)
    self.form.verticalLayout.insertWidget(0, f.web)
    addHook('reset', self.refresh)
    #########################################################
    restoreGeom(self, self.name)
    b = f.buttonBox.addButton(_("Save Image"), QDialogButtonBox.ActionRole)
    b.clicked.connect(self.browser)
    b.setAutoDefault(False)
    c = self.connect
    s = SIGNAL("clicked()")
    c(f.groups, s, lambda: self.changeScope("deck"))
    f.groups.setShortcut("g")
    c(f.all, s, lambda: self.changeScope("collection"))
    c(f.month, s, lambda: self.changePeriod(0))
    c(f.year, s, lambda: self.changePeriod(1))
    c(f.life, s, lambda: self.changePeriod(2))
    c(f.web, SIGNAL("loadFinished(bool)"), self.loadFin)
    maybeHideClose(self.form.buttonBox)
    addCloseShortcut(self)
    self.refresh()
    self.show()  # show instead of exec in order for browser to open properly

def deckStatsReject(self):
    # clean up after ourselves:
    remHook('reset', self.refresh)

def initializeViews():
    CollectionStats.dueGraph = wrap(
        CollectionStats.dueGraph, collectionStatsDueGraph, "around")
    Overview._body = ov_body
    Overview._renderPage = overviewRenderPage
    DeckBrowser._renderStats = wrap(
        DeckBrowser._renderStats, deckbrowserRenderStats, "around")
    if ANKI21:
        DeckStats.__init__ = wrap(DeckStats.__init__, deckStatsInit21, "after")
    else:
        DeckStats.__init__ = deckStatsInit20
    DeckStats.reject = wrap(DeckStats.reject, deckStatsReject)
