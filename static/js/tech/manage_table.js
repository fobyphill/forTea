function show_hide_select(this_select){
    let s_link = document.getElementById('s_link')
    if (this_select.value == 'link')
        s_link.style.display = 'inline'
    else s_link.style.display = 'none'
}

function add_field(){
    let add = document.createElement('input')
    add.type = 'hidden'
    add.name = 'b_add'
    let form = document.getElementById('form')
    form.appendChild(add)
    form.submit()
}

function change_table_del(this_table){
    let fields = document.getElementsByName(this_table.value)
    let fields_del = document.getElementById('s_field_del')
    fields_del.innerHTML = ''
    for (let i = 0; i < fields.length; i++){
        let opt = document.createElement('option')
        opt.value=fields[i].id
        opt.innerText = fields[i].innerText
        fields_del.appendChild(opt)
    }
}

function delete_field() {
    let del = document.createElement('input')
    del.type = 'hidden'
    del.name = 'b_delete'
    let form = document.getElementById('form_delete_field')
    form.appendChild(del)
    form.submit()
}
