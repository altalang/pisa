#from altareporting import Label
from pisa_reportlab import PmlParagraph
from reportlab_paragraph import FragLine, ParaLines, _handleBulletWidth
from reportlab.pdfbase.pdfmetrics import stringWidth, getAscentDescent
import sys
from string import whitespace

try:
    import pyfribidi
except:
    try:
        import pyfribidi2 as pyfribidi
    except:
        pyfribidi = None

try:
    import PyICU
except:
    pass

_cached_line_iterators = {}

LEADING_FACTOR = 1.0

def has_thai(line):
    for character in line:
        if 0x0e00 < ord(character) < 0x0e7f:
            return True

    return False


def split(line):
    if not sys.modules.has_key('PyICU'):
        return line.split(' ')

    # check if the text contains any Thai-block characters
    #has_thai = False
    #for character in line:
    #    if 0x0e00 < ord(character) < 0x0e7f:
    #        has_thai = True
    #        break

    # get the appropriate locale
    if has_thai(line):
        icu_locale = PyICU.Locale('th')
    else:
        icu_locale = PyICU.Locale.getDefault()

    # get the iterator
    iterator = _cached_line_iterators.get(icu_locale.getBaseName())
    if not iterator:
        iterator = PyICU.BreakIterator.createLineInstance(icu_locale)
        _cached_line_iterators[icu_locale.getBaseName()] = iterator

    # split the line using the iterator
    words = []
    last_position = 0
    iterator.setText(line)
    for position in iterator:
        words.append(line[last_position:position])
        last_position = position

    return words


#def split(text, delim=None):
#    if type(text) is str:
#        text = text.decode('utf8')
#    if type(delim) is str:
#        delim = delim.decode('utf8')
#    elif delim is None and u'\xa0' in text:
#        return [uword.encode('utf8') for uword in _wsc_re_split(text)]
#
#    return [uword.encode('utf8') for uword in text.split(delim)]

def _getFragWords(frags, use_bidi=False):
   ''' given a Parafrag list return a list of fragwords
       [[size, (f00,w00), ..., (f0n,w0n)],....,[size, (fm0,wm0), ..., (f0n,wmn)]]
       each pair f,w represents a style and some string
       each sublist represents a word
   '''
   R = [] # the collection of frag information
   W = [] # a frag per word
   n = 0  # width of the frag
   hangingStrip = False

   for f in frags:
       text = f.text

       if use_bidi and pyfribidi:
           text = pyfribidi.log2vis(text)

            # PDF renderers commonly mishandle uFEFF, but it's safe to delete it, so do that now.
           if u'\ufeff' in text:
               text = u''.join([c for c in text if c != u'\ufeff'])

       else:
           is_indic = False
           for c in text:
               if 2304 <= ord(c) <= 3071 or 3398 <= ord(c) <= 3415 or 4096 <= ord(c) <= 4191:
                   is_indic = True
                   break

           if is_indic:
               dependent_vowels = (u'\u0a3f',  u'\u0bc6', u'\u0bc7', u'\u0bc8', u'\u09bf', u'\u09c7',
                    u'\u09c8', u'\u0d46', u'\u0d47', u'\u0d48', u'\u093f', u'\u0b47', u'\u0abf', u'\u1031',
                    u'\u0dd9', u'\u0ddb')

               text = [c for c in text]
               k = 1
               for c in text[1:]:
                   if c in dependent_vowels:
                       text[k-1], text[k] = text[k], text[k-1]
                   k += 1

               text = u''.join(text)


       #del f.text # we can't do this until we sort out splitting
                   # of paragraphs
       if text!='':
           if hangingStrip:
               hangingStrip = False
               text = text.lstrip()
           #if type(text) is str:
           #    text = text.decode('utf8')
           S = split(text)
           if S==[]: S = ['']

           # not sure what's going on here yet
           if W!=[] and text[0] in whitespace:
               W.insert(0,n)
               R.append(W)
               W = []
               n = 0

           # loop through all but the last word
           for w in S[:-1]:
               W.append((f,w))
               n += stringWidth(w, f.fontName, f.fontSize)
               W.insert(0,n)
               R.append(W)
               W = []
               n = 0

           # handle the last word
           # WTF IS ALL OF THIS.

           # set the word to the last word, because we skipped it in the for loop above
           w = S[-1]
           W.append((f,w))
           n += stringWidth(w, f.fontName, f.fontSize)
           # if the last character in the text is whitespace
           # then go ahead and add the wordfrag structure
           # otherwise it will be caught by the last if W != []
           # and the exact same thing will happen.. WTF
           # ^ but only if this is the last frag
           # otherwise this frag gets included in with something else
           # W is not always length = 2 when it is appended
           if text and text[-1] in whitespace:
               W.insert(0,n)
               R.append(W)
               W = []
               n = 0
       #elif hasattr(f,'cbDefn'):
       #    w = getattr(f.cbDefn,'width',0)
       #    if w:
       #        if W!=[]:
       #            W.insert(0,n)
       #            R.append(W)
       #            W = []
       #            n = 0
       #        R.append([w,(f,'')])
       #    else:
       #        W.append((f,''))
       elif hasattr(f, 'lineBreak'):
           #pass the frag through.  The line breaker will scan for it.
           if W!=[]:
               W.insert(0,n)
               R.append(W)
               W = []
               n = 0
           R.append([0,(f,'')])
           hangingStrip = True

   if W!=[]:
       W.insert(0,n)
       R.append(W)

   return R

class AltaParagraph(PmlParagraph):

    def __init__(self, text, style, bulletText=None, frags=None, caseSensitive=True, encoding='utf8', use_bidi=False):
        self.use_bidi = use_bidi
        PmlParagraph.__init__(self, text, style, bulletText, frags, caseSensitive, encoding)

    def wrap(self, availWidth, availHeight):

        availHeight = self.setMaxHeight(availHeight)

        style = self.style

        self.deltaWidth = style.paddingLeft + style.paddingRight + style.borderLeftWidth + style.borderRightWidth
        self.deltaHeight = style.paddingTop + style.paddingBottom + style.borderTopWidth + style.borderBottomWidth

        # reduce the available width & height by the padding so the wrapping
        # will use the correct size
        availWidth -= self.deltaWidth
        availHeight -= self.deltaHeight

        # Modify maxium image sizes
        self._calcImageMaxSizes(availWidth, self.getMaxHeight() - self.deltaHeight)

        self._wrap(availWidth, availHeight)

        #self.height = max(1, self.height)
        #self.width = max(1, self.width)

        # increase the calculated size by the padding
        self.width = self.width + self.deltaWidth
        self.height = self.height + self.deltaHeight

        return (self.width, self.height)

    def _wrap(self, availWidth, availHeight):

        # work out widths array for breaking
        self.width = availWidth
        style = self.style
        leftIndent = style.leftIndent
        first_line_width = availWidth - (leftIndent+style.firstLineIndent) - style.rightIndent
        later_widths = availWidth - leftIndent - style.rightIndent

        if style.wordWrap == 'CJK':
            #use Asian text wrap algorithm to break characters
            blPara = self.breakLinesCJK([first_line_width, later_widths])
        else:
            blPara = self.breakLines([first_line_width, later_widths])

        self.blPara = blPara
        autoLeading = getattr(self,'autoLeading',getattr(style,'autoLeading',''))
        leading = style.leading
        if blPara.kind==1 and autoLeading not in ('','off'):
            height = 0
            if autoLeading=='max':
                for l in blPara.lines:
                    height += max(l.ascent-l.descent,leading)
            elif autoLeading=='min':
                for l in blPara.lines:
                    height += l.ascent - l.descent
            else:
                raise ValueError('invalid autoLeading value %r' % autoLeading)
        else:
            if autoLeading=='max':
                leading = max(leading,LEADING_FACTOR*style.fontSize)
            elif autoLeading=='min':
                leading = LEADING_FACTOR*style.fontSize
            height = len(blPara.lines) * leading
        self.height = height

        return self.width, height

    def breakLines(self, width):
        """
        Returns a broken line structure. There are two cases

        A) For the simple case of a single formatting input fragment the output is
            A fragment specifier with
                - kind = 0
                - fontName, fontSize, leading, textColor
                - lines=  A list of lines

                        Each line has two items.

                        1. unused width in points
                        2. word list

        B) When there is more than one input formatting fragment the output is
            A fragment specifier with
               - kind = 1
               - lines=  A list of fragments each having fields
                            - extraspace (needed for justified)
                            - fontSize
                            - words=word list
                                each word is itself a fragment with
                                various settings

        This structure can be used to easily draw paragraphs with the various alignments.
        You can supply either a single width or a list of widths; the latter will have its
        last item repeated until necessary. A 2-element list is useful when there is a
        different first line indent; a longer list could be created to facilitate custom wraps
        around irregular objects."""

        if self.debug:
            print id(self), "breakLines"

        if not isinstance(width,(tuple,list)): maxWidths = [width]
        else: maxWidths = width
        lines = []
        lineno = 0
        style = self.style

        #for bullets, work out width and ensure we wrap the right amount onto line one
        _handleBulletWidth(self.bulletText,style,maxWidths)

        maxWidth = maxWidths[0]

        self.height = 0
        autoLeading = getattr(self,'autoLeading',getattr(style,'autoLeading',''))
        calcBounds = autoLeading not in ('','off')
        frags = self.frags
        nFrags= len(frags)
        if nFrags==1 and not hasattr(frags[0],'cbDefn'):
            f = frags[0]
            fontSize = f.fontSize
            fontName = f.fontName
            ascent, descent = getAscentDescent(fontName,fontSize)

            # wordsplit is here
            if hasattr(f, 'text'):
                words = split(f.text)
                if not words and hasattr(f, 'words'):
                    words = f.words
            else:
                words = f.words

            #words = hasattr(f,'text') and split(f.text, ' ') or f.words

            spaceWidth = stringWidth(' ', fontName, fontSize, self.encoding)
            cLine = []
            currentWidth = -spaceWidth   # hack to get around extra space for word 1
            for word in words:
                #this underscores my feeling that Unicode throughout would be easier!
                wordWidth = stringWidth(word, fontName, fontSize, self.encoding)
                newWidth = currentWidth + spaceWidth + wordWidth
                if newWidth <= maxWidth or not len(cLine):
                    # fit one more on this line
                    cLine.append(word)
                    currentWidth = newWidth
                else:
                    if currentWidth > self.width: self.width = currentWidth
                    #end of line
                    lines.append((maxWidth - currentWidth, cLine))
                    cLine = [word]
                    currentWidth = wordWidth
                    lineno += 1
                    try:
                        maxWidth = maxWidths[lineno]
                    except IndexError:
                        maxWidth = maxWidths[-1]  # use the last one

            #deal with any leftovers on the final line
            if cLine!=[]:
                if currentWidth>self.width: self.width = currentWidth
                lines.append((maxWidth - currentWidth, cLine))

            return f.clone(kind=0, lines=lines,ascent=ascent,descent=descent,fontSize=fontSize)
        elif nFrags<=0:
            return ParaLines(kind=0, fontSize=style.fontSize, fontName=style.fontName,
                            textColor=style.textColor, ascent=style.fontSize,descent=-0.2*style.fontSize,
                            lines=[])
        else:
            #if hasattr(self,'blPara') and getattr(self,'_splitpara',0):
            #    #NB this is an utter hack that awaits the proper information
            #    #preserving splitting algorithm
            #    return self.blPara
            n = 0

            # words is not a list of texts
            # it's a list of fragments, that is only ever size one or zero
            words = []
            wordfrags = []

            for fragment in frags:
                fragment_words = _getFragWords([fragment], use_bidi=self.use_bidi)
                if self.use_bidi:
                    fragment_words.reverse()
                wordfrags += fragment_words

            for w in wordfrags:
                # f is the frag
                f=w[-1][0]
                fontName = f.fontName
                fontSize = f.fontSize
                if sys.modules.has_key('PyICU'):
                    spaceWidth = 0
                else:
                    spaceWidth = stringWidth(' ',fontName, fontSize)

                # if at the beginning of a line
                if not words:
                    currentWidth = -spaceWidth   # hack to get around extra space for word 1
                    maxSize = fontSize
                    maxAscent, minDescent = getAscentDescent(fontName,fontSize)

                wordWidth = w[0]
                f = w[1][0]
                if wordWidth>0:
                    newWidth = currentWidth + spaceWidth + wordWidth
                else:
                    newWidth = currentWidth
                # newWidth is is essentially the proposed width of
                # previous width of line plus the next(current) word

                #test to see if this frag is a line break. If it is we will only act on it
                #if the current width is non-negative or the previous thing was a deliberate lineBreak
                lineBreak = hasattr(f,'lineBreak')
                endLine = (newWidth>maxWidth and n>0) or lineBreak
                # we never hit linebreak
                # so this is testing if newWidth is too large
                if not endLine:
                    if lineBreak: continue      #throw it away
                    # nText is the actual word
                    nText = w[1][1]
                    if nText: n += 1
                    fontSize = f.fontSize
                    if calcBounds:
                        #cbDefn = getattr(f,'cbDefn',None)
                        #if getattr(cbDefn,'width',0):
                        #    descent,ascent = imgVRange(cbDefn.height,cbDefn.valign,fontSize)
                        #else:
                        ascent, descent = getAscentDescent(f.fontName,fontSize)
                    else:
                        ascent, descent = getAscentDescent(f.fontName,fontSize)
                    maxSize = max(maxSize,fontSize)
                    maxAscent = max(maxAscent,ascent)
                    minDescent = min(minDescent,descent)
                    if not words:
                        g = f.clone()
                        words = [g]
                        # g.text = nText
                        g.text = [nText]
                    #elif not _sameFrag(g,f):
                    #    if currentWidth>0 and ((nText!='' and nText[0]!=' ') or hasattr(f,'cbDefn')):
                    #        #if hasattr(g,'cbDefn'):
                    #        #    i = len(words)-1
                    #        #    while i>=0:
                    #        #        wi = words[i]
                    #        #        cbDefn = getattr(wi,'cbDefn',None)
                    #        #        if cbDefn:
                    #        #            if not getattr(cbDefn,'width',0):
                    #        #                i -= 1
                    #        #                continue
                    #        #        if not wi.text.endswith(' '):
                    #        #            wi.text += ' '
                    #        #        break
                    #        #else:
                    #        if not g.text.endswith(' '):
                    #            g.text += ' '
                    #    g = f.clone()
                    #    words.append(g)
                    #    g.text = nText
                    else:
                        #if nText!='' and nText[0]!=' ':
                        if nText != '':
                            #g.text += ' ' + nText
                            g.text.append(nText)

                    #for i in w[2:]:
                    #    g = i[0].clone()
                    #    g.text=i[1]
                    #    words.append(g)
                    #    fontSize = g.fontSize
                    #    if calcBounds:
                    #        #cbDefn = getattr(g,'cbDefn',None)
                    #        #if getattr(cbDefn,'width',0):
                    #        #    descent,ascent = imgVRange(cbDefn.height,cbDefn.valign,fontSize)
                    #        #else:
                    #        ascent, descent = getAscentDescent(g.fontName,fontSize)
                    #    else:
                    #        ascent, descent = getAscentDescent(g.fontName,fontSize)
                    #    maxSize = max(maxSize,fontSize)
                    #    maxAscent = max(maxAscent,ascent)
                    #    minDescent = min(minDescent,descent)

                    currentWidth = newWidth
                else:  #either it won't fit, or it's a lineBreak tag
                    if lineBreak:
                        g = f.clone()
                        #del g.lineBreak
                        words.append(g)
                        g.text = []

                    if currentWidth>self.width: self.width = currentWidth
                    #end of line
                    if self.use_bidi:
                        words.reverse()
                    for item in words:
                        if self.use_bidi:
                            item.text.reverse()
                        if sys.modules.has_key('PyICU'):
                            item.text = ''.join(item.text)
                        else:
                            item.text = ' '.join(item.text)

                    lines.append(FragLine(extraSpace=maxWidth-currentWidth, wordCount=n,
                                          lineBreak=lineBreak, words=words, fontSize=maxSize,
                                          ascent=maxAscent, descent=minDescent))

                    #start new line
                    lineno += 1

                    # attempt to reset the maxWidth of the new line
                    try:
                        maxWidth = maxWidths[lineno]
                    except IndexError:
                        maxWidth = maxWidths[-1]  # use the last one

                    if lineBreak:
                        n = 0
                        words = []
                        continue

                    # because there was no linebreak
                    # reuse the current word as the first word of the next line
                    currentWidth = wordWidth
                    n = 1
                    g = f.clone()
                    maxSize = g.fontSize
                    if calcBounds:
                        #cbDefn = getattr(g,'cbDefn',None)
                        #if getattr(cbDefn,'width',0):
                        #    minDescent,maxAscent = imgVRange(cbDefn.height,cbDefn.valign,maxSize)
                        #else:
                        maxAscent, minDescent = getAscentDescent(g.fontName,maxSize)
                    else:
                        maxAscent, minDescent = getAscentDescent(g.fontName,maxSize)
                    words = [g]
                    #g.text = w[1][1]
                    g.text = [w[1][1]]

                    #for i in w[2:]:
                    #    g = i[0].clone()
                    #    g.text=i[1]
                    #    words.append(g)
                    #    fontSize = g.fontSize
                    #    if calcBounds:
                    #        #cbDefn = getattr(g,'cbDefn',None)
                    #        #if getattr(cbDefn,'width',0):
                    #        #    descent,ascent = imgVRange(cbDefn.height,cbDefn.valign,fontSize)
                    #        #else:
                    #        ascent, descent = getAscentDescent(g.fontName,fontSize)
                    #    else:
                    #        ascent, descent = getAscentDescent(g.fontName,fontSize)
                    #    maxSize = max(maxSize,fontSize)
                    #    maxAscent = max(maxAscent,ascent)
                    #    minDescent = min(minDescent,descent)

            # end for loop

            #deal with any leftovers on the final line
            if words != []:
                if currentWidth>self.width: self.width = currentWidth
                if self.use_bidi:
                    words.reverse()
                for item in words:
                    if self.use_bidi:
                        item.text.reverse()
                    if sys.modules.has_key('PyICU'):
                        item.text = ''.join(item.text)
                    else:
                        item.text = ' '.join(item.text)

                lines.append(ParaLines(extraSpace=(maxWidth - currentWidth),wordCount=n,
                                    words=words, fontSize=maxSize,ascent=maxAscent,descent=minDescent))

            return ParaLines(kind=1, lines=lines)

        return lines

   # def split(self, availWidth, availHeight):
   #     return []

