window.addEventListener("load", ready);

function qsa() {
    console.log(document.querySelectorAll('textarea'));
    return Array.apply(null, document.querySelectorAll('textarea'));
}

function ta_to_editor(editorEl) {
    const editor = CodeMirror.fromTextArea(editorEl, {
        mode: {
            name: "python",
            version: 3,
            singleLineStringErrors: false
        },
        autoRefresh: true,
        lineNumbers: true,
        indentUnit: 4,
        extraKeys: {
            "Ctrl-Space": "autocomplete"
        },
        matchBrackets: true
    });
    editor.on('change', (editor) => {
        const text = editor.doc.getValue()
        document.getElementById(editorEl.id).value = text;
        //console.log(text);
    })
    hyperlinkOverlay(editor);
}

function ready() {
    qsa().forEach((editorEl) => ta_to_editor(editorEl))
}

function hoverWidgetOnOverlay(cm, overlayClass, widget) {
    cm.addWidget({line:0, ch:0}, widget, true);
    widget.style.position = 'fixed';
    widget.style.zIndex=100000;
    widget.style.top=widget.style.left='-1000px'; // hide it
    widget.dataset.token=null;
    cm.getWrapperElement().addEventListener('mousemove', e => {
        let onToken=e.target.classList.contains("cm-"+overlayClass), onWidget=(e.target===widget || widget.contains(e.target));

        if (onToken && e.target.innerText!==widget.dataset.token) { // entered token, show widget
            var rect = e.target.getBoundingClientRect();
            widget.style.left=rect.left+'px';
            widget.style.top=rect.bottom+'px';

            widget.dataset.token=e.target.innerText;
            if (typeof widget.onShown==='function') widget.onShown();

        } else if ((e.target===widget || widget.contains(e.target))) { // entered widget, call widget.onEntered
            if (widget.dataset.entered==='true' && typeof widget.onEntered==='function')  widget.onEntered();
            widget.dataset.entered='true';

        } else if (!onToken && widget.style.left!=='-1000px') { // we stepped outside
            widget.style.top=widget.style.left='-1000px'; // hide it
            delete widget.dataset.token;
            widget.dataset.entered='false';
            if (typeof widget.onHidden==='function') widget.onHidden();
        }
        return true;
    });
}


function hyperlinkOverlay(cm) {
    if (!cm) return;

    const rx_word = "\" "; // Define what separates a word

    function isUrl(s) {
        if (!isUrl.rx_url) {
            // taken from https://gist.github.com/dperini/729294
            isUrl.rx_url='\[\[((?:table\.|contract\.|)(?:[\d\w]+\.)*[\d\w]+)\]\]';

            // valid prefixes
              isUrl.prefixes=['[['];
              isUrl.domains=[']]'];
        }

        //if (!isUrl.rx_url.test(s)) return false;
        for (let i=0; i<isUrl.prefixes.length; i++) if (s.startsWith(isUrl.prefixes[i])) return true;
        for (let i=0; i<isUrl.domains.length; i++) if (s.endsWith('.'+isUrl.domains[i]) || s.includes('.'+isUrl.domains[i]+'\/') ||s.includes('.'+isUrl.domains[i]+'?')) return true;
        return false;
    }
    cm.addOverlay({
        token: function(stream) {
            let ch = stream.peek();
            let word = "";

            if (rx_word.includes(ch) || ch==='\uE000' || ch==='\uE001') {
                stream.next();
                return null;
            }

            while ((ch = stream.peek()) && !rx_word.includes(ch)) {
                word += ch;
                stream.next();
            }

            if (isUrl(word)) return "url"; // CSS class: cm-url
        }},
        { opaque : true }  // opaque will remove any spelling overlay etc
    );
    let widget=document.createElement('button');
    widget.innerHTML='&rarr;'
    widget.onclick=function(e) {
        if (!widget.dataset.token) return;
        let link=widget.dataset.token;
        //if (!(new RegExp('^(?:(?:contract?|table):\/\/)', 'i')).test(link)) link="http:\/\/"+link;
        // open first link on value - where [[ and ]] with space after ]]
        // fixme: regexp +
        if (link === 'null'){}
        else if (link.includes("contract.")){
         // if link contains contract - on manage-class-tree, that mains what - window open on contract
            var parts = link.split('.', 2);
            var id_contract = parts[1];
            window.open("\/manage-contracts?i_id="+id_contract, '_blank');
        }
        else if (link.includes("table.")){
            var parts = link.split('.', 2);
            var id_table = parts[1];
            window.open("\/manage-object?class_id="+id_table, '_blank');
        }
        else{
            var parts = link.split('.'); // not sure how many points
            if (parts.length == 1){
                var id_table = parts[0].split(/(\d+)/); // may be [[ 624 ]] something
                var id_object = id_table[1];
                console.log(id_object);
                window.open("\/manage-class-tree?i_id="+id_object, '_blank');

            }   // - short link - or const
            else{
                var id_table = parts[0].split(/(\d+)/); // may be [[ 624 ]] something
                var id_object = id_table[1];
                console.log(id_object);
                window.open("\/manage-class-tree?i_id="+id_object, '_blank');
            }
        };

        return true;
    };
    hoverWidgetOnOverlay(cm, 'url', widget);
}