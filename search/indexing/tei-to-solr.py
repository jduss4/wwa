#! /usr/bin/env python
# coding=UTF-8
""" Index fields from SGA TEI to a Solr instance"""

import os, sys, re
import solr
import xml.sax, json
from lxml import etree
 
class Doc :
    def __init__(self, 
        solr="", 
        shelfmark="",
        shelf_label="",
        viewer_url="",
        work="",
        authors="",
        attribution="",
        doc_id=None, 
        text="", 
        hands={"mws":"","pbs":"", "comp":"", "library":"", "ww":"", "unk":""}, 
        mod={"add":[],"del":[],"hi":[]}, 
        hands_pos={"mws":[], "pbs":[], "comp":[], "library":[], "ww":[], "unk":[]}, 
        hands_tei_pos={"mws":[], "pbs":[], "comp":[], "library":[], "ww":[], "unk":[]},
        mod_pos={"add":[],"del":[],"hi":[]}):
      
        # Solr connection
        self.solr = solr

        # General fields
        self.shelfmark = shelfmark
        self.doc_id = doc_id

        # Text and positions
        # TODO: determine hand fields from source TEI - they are dynamic fields in Solr. 
        # Do the same with their positions.
        self.text = text
        self.hands = hands
        self.mod = mod
        self.hands_pos = hands_pos
        self.hands_tei_pos = hands_tei_pos
        self.mod_pos = mod_pos


    def commit(self):
        # print "id: %s\nshelf: %s\ntext: %s\nhands: %s\nmod: %s\nhands_pos: %s\nmod_pos: %s\n" % (self.doc_id, self.shelfmark, self.text, self.hands, self.mod, self.hands_pos, self.mod_pos)
        # print "id: %s\nhi: %s\n" % (self.doc_id, self.hands["ww"].decode('utf-8'))
        # return 0
        self.solr.add(id=self.doc_id, 
            shelfmark=self.shelfmark, 
            shelf_label=self.shelf_label,
            viewer_url = self.viewer_url,
            work=self.work,
            # authors=self.authors,
            # attribution=self.attribution,
            text=self.text, 
            hand_mws=self.hands["mws"], 
            hand_pbs=self.hands["pbs"], 
            hand_comp=self.hands["comp"],
            hand_library=self.hands["library"], 
            hand_ww=self.hands["ww"],
            hand_unknown=self.hands["unk"],  
            added=self.mod["add"], 
            deleted=self.mod["del"],
            highlighted=self.mod["hi"],
            mws_pos=self.hands_pos["mws"], 
            pbs_pos=self.hands_pos["pbs"],
            comp_pos=self.hands_pos["comp"],
            library_pos=self.hands_pos["library"],
            ww_pos=self.hands_pos["ww"],
            unknown_pos=self.hands_pos["unk"],
            add_pos=self.mod_pos["add"], 
            del_pos=self.mod_pos["del"])
        self.solr.commit()

class GSAContentHandler(xml.sax.ContentHandler):
    def __init__(self, s, filename):
        xml.sax.ContentHandler.__init__(self)

        self.solr = s
        self.pos = 0
        self.hands = ["unk"]        
        self.latest_hand = self.hands[-1]
        self.hand_start = 0
        self.path = [] # name, hand
        self.cur_attrs = []

        self.addSpan = {"id": "", "hand": None}
        self.delSpan = None
        self.hiSpan = None

        self.handShift = False

        self.filename = filename

        # Initialize doc
        self.doc = Doc(
            solr = self.solr)

        print self.doc
        #purge 
        self.doc.shelfmark=""
        shelf_label=""
        viewer_url = ""
        work=""
        authors=""
        attribution=""
        self.doc.doc_id=None
        self.doc.text=""
        self.doc.hands={"mws":"","pbs":"", "comp":"", "library":"", "ww":"", "unk":""}
        self.doc.mod={"add":[],"del":[],"hi":[]}
        self.doc.hands_pos={"mws":[], "pbs":[], "comp":[], "library":[], "ww":[], "unk":[]}
        self.doc.hands_tei_pos={"mws":[], "pbs":[], "comp":[], "library":[], "ww":[], "unk":[]}
        self.doc.mod_pos={"add":[],"del":[],"hi":[]}
 
    def startElement(self, name, attrs):
        # add element to path stack
        self.path.append([name, self.hands[-1]])
        self.cur_attrs.append(attrs)

        if name == "surface":
            if "partOf" in attrs:
                partOf = attrs["partOf"] if "partOf" in attrs else " "
                # self.doc.shelfmark = partOf[1:] if partOf[0] == "#" else partOf
            self.doc.doc_id = attrs["xml:id"]

            parts = self.doc.doc_id.split('-')
            self.doc.viewer_url = "/wwa/?mf=%s#/p%d/" % (parts[0], int(parts[1]))
            self.doc.shelfmark = parts[0]

            source = open(xml_dir + self.doc.shelfmark + '-header.xml')
            meta = etree.parse(source).getroot()
            NS = "http://www.tei-c.org/ns/1.0"
            
            self.doc.work = meta.find(".//{%s}fileDesc//{%s}titleStmt//{%s}title[@level='m'][@type='main']" % (NS,NS,NS)).text
            if self.doc.work == None:
                self.doc.work = "Untitled"
            self.doc.shelf_label = meta.find(".//{%s}fileDesc//{%s}sourceDesc//{%s}bibl/{%s}idno" % (NS,NS,NS,NS)).text
            if self.doc.shelf_label == None:
                self.doc.shelf_label = "Unknown"

        if "hand" in attrs:
            if not (name == "hi" and attrs["hand"] == "#ww"):
                hand = attrs["hand"]
                if len(hand) > 0:
                    if hand[0]=="#": hand = hand[1:]
                    self.hands.append(hand)
                    self.path[-1][-1] = hand

        if "type" in attrs:
            if attrs["type"] == "library":
                hand = "library"
                self.hands.append(hand)
                self.path[-1][-1] = hand

        # Create a new added section
        if name == "add" or name == 'addSpan':
            self.doc.mod["add"].append("")            
            self.doc.mod_pos["add"].append(str(self.pos)+":") 
        if name == "del" or name == 'delSpan':
            self.doc.mod["del"].append("")
            self.doc.mod_pos["del"].append(str(self.pos)+":")
        # WWA has spans for highlighted text
        if (name == "hi" and "hand" in attrs) or (name == 'metamark' and "function" in attrs and attrs["function"] == "marginalia"):
            self.doc.mod["hi"].append("")            
            self.doc.mod_pos["hi"].append(str(self.pos)+":") 

        if name == "addSpan":
            spanTo = attrs["spanTo"] if "spanTo" in attrs else " "
            self.addSpan["id"] = spanTo[1:] if spanTo[0] == "#" else spanTo
            if "hand" in attrs:
                self.addSpan["hand"] = attrs["hand"]

        if name == "delSpan":
            spanTo = attrs["spanTo"] if "spanTo" in attrs else " "
            self.delSpan = spanTo[1:] if spanTo[0] == "#" else spanTo

        if name == 'metamark' and "function" in attrs and attrs["function"] == "marginalia":
            spanTo = attrs["spanTo"] if "spanTo" in attrs else " "
            if len(spanTo) > 0:
                self.hiSpan = spanTo[1:] if spanTo[0] == "#" else spanTo

        # if this is the anchor of and (add|del)Span, close the addition/deletion
        if name == "anchor":
            if "xml:id" in attrs:
                if attrs["xml:id"] == self.addSpan:

                    # If the anchor corresponds to and addSpan with @hand, remove the hand from stack
                    if self.addSpan["hand"] != None:
                        if len(self.path) > 1 and self.hands[-1] != self.path[-2][-1]:
                            self.hands.pop()
                    # reset addSpan
                    self.addSpan["id"] = ""
                    self.addSpan["hand"] = None
                    self.doc.mod_pos["add"][-1] += str(self.pos)
                if attrs["xml:id"] == self.delSpan:
                    self.delSpan = None
                    self.doc.mod_pos["del"][-1] += str(self.pos)

                #WWA
                if attrs["xml:id"] == self.hiSpan:
                    self.hiSpan = None
                    self.doc.mod_pos["hi"][-1] += str(self.pos)

        if name == "handShift":
            if "new" in attrs:                
                hand = attrs["new"]
                if hand[0]=="#": hand = hand[1:]
                if hand == "ww": 
                    self.handShift = True
                    self.hands.append(hand)
                    self.path[-1][-1] = hand

                # print self.hands, self.path

 
    def endElement(self, name):
        # Remove hand from hand stack if this is the last element with that hand
        # Unless it's an addSpan with hand, in which case we defer to the corresponding anchor
        # Here we are assuming that there is only one handShift per page.
        if not self.handShift and name != "addSpan" and self.addSpan["hand"] == None:
            if len(self.path) > 1 and self.hands[-1] != self.path[-2][-1]:
                self.hands.pop()

        ### SPECIAL CASES ###
        if self.doc.doc_id == "ox-ms_abinger_c58-0057" and self.path[-1][-1] == "mws":
            # self.hands.pop()
            self.hands.append("pbs")
                
        # Remove the element from element stack
        self.path.pop()
        # Remove the attributes from the attributes stack
        self.cur_attrs.pop()

        if name == "surface":
            self.doc.end = self.pos
            self.doc.commit()

            print "**** end of file" 

        if name == "add":
             self.doc.mod_pos["add"][-1] += str(self.pos)

        if name == "del":
             self.doc.mod_pos["del"][-1] += str(self.pos)

 
    def characters(self, content):
        # Has the hand changed? If yes, write positions and keep track of new starting point
        if self.latest_hand != self.hands[-1]:
            # Add extra space between hand occurences (will need to consider this when mapping to positions)
            self.doc.hands[self.latest_hand] += " "
            self.doc.hands_pos[self.latest_hand].append(str(self.hand_start)+":"+str(self.pos))
            self.latest_hand = self.hands[-1]
            self.hand_start = self.pos + 1

        # if this is a descendant of add|del or we are in an (add|del)Span area, add content to added/deleted
        elements = [e[0] for e in self.path]
        if 'add' in elements or self.addSpan["id"] != "":
            self.doc.mod["add"][-1] += content
        if 'del' in elements or self.delSpan:
            self.doc.mod["del"][-1] += content
        # if this is a descendant of hi[@hand], or we are in a span area, add the content, add content to highlighted
        if ('hi' in elements and "hand" in self.cur_attrs[-1]) or self.hiSpan:
            self.doc.mod["hi"][-1] += content

        # Add text to current hand and to full-text field
        self.doc.hands[self.hands[-1]] += content
        self.doc.text += content

        # Update current position
        self.pos += len(content)
 
if __name__ == "__main__":

    if len(sys.argv) != 3:
        print 'Usage: ./tei-to-solr.py path_to_tei path_to_manifests'
        sys.exit(1)

    # Connect to solr instance
    s = solr.SolrConnection('http://localhost:8080/solr/wwa')

    # Walk provided directory for xml files; parse them and create/commit documents
    xml_dir = os.path.normpath(sys.argv[1]) + os.sep
    for f in os.listdir(xml_dir):
        p = re.compile(r'\w{3}\.\d{5}-\d{4}\.xml')
        if p.match(f):
            source = open(xml_dir + f)
            xml.sax.parse(source, GSAContentHandler(s, f))
            source.close()
