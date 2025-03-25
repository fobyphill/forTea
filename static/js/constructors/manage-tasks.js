

window.onload = function(){
    let my_unit = JSON.parse($('#s_my_unit').html())
    if (my_unit.kind === 'custom'){
        my_linkmap = my_unit.lm
        acilm(my_linkmap, true)
    }
    // Enter в полях блока Управления
    $('#i_search').keypress(function(e) {
        if(e.keyCode === 13)
            send_form_with_param('b_search')
    })
}


function new_task(){
    let i_id = $('#i_task_id')
    let parent_id = i_id.val()
    i_id.val('')
    $('#i_parent').val(parent_id)
    $('#i_name').val('')
    $('#span_kind').attr('class', 'tag-invis')
    let sel_kind = $('#sel_kind')
    sel_kind.attr('class', 'form-control')
    sel_kind.val('folder')
    $('#b_delete').attr('disabled', true)
    $('#b_save').attr('disabled', true)
    $('#div_params').attr('class', 'tag-invis')
    let old_br = $('#ta_br')[0]
    let parent_br = old_br.parentNode
    parent_br.removeChild(old_br)
    let br = document.createElement('textarea')
    br.id = 'ta_br'
    br.name = 'ta_br'
    parent_br.appendChild(br)
    $('#div_lm').html('<button class="btn btn-outline-info" onclick="acilm(\'new\', true)" id="b_acilm">+</button>')
    let old_tr = $('#ta_tr')[0]
    let parent_tr = old_tr.parentNode
    parent_tr.removeChild(old_tr)
    let tr = document.createElement('textarea')
    tr.id = 'ta_tr'
    tr.name = 'ta_tr'
    parent_tr.appendChild(tr)
    $('div.CodeMirror').remove()
    ready()
    $('#b_add_del_object').remove()
}

function task_valid(){
    let not_valid = false
    if (!$('#i_name').val())
        not_valid = true
    $('#b_save').attr('disabled', not_valid)
}

function change_branch(this_branch){
    let childs = this_branch.children
    let first_sym = '+'
    let class_name = 'tag-invis'
    if (childs[2].className === 'tag-invis'){
        first_sym = '-'
        class_name = ''
    }
    childs[2].className = class_name
    this_branch.innerHTML = first_sym + this_branch.innerHTML.slice(1)
}


function save_task(){
    let link_map = palimafos(true)
    $('#i_linkmap').val(JSON.stringify(link_map))
    send_form_with_param('b_save')
}


function check_enter(this_input, param_name){
    if (event.keyCode === 13)
        send_form_with_param(param_name)
}