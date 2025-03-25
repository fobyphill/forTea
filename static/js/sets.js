function add_const(this_button, postfix){
    this_button.remove()
    let table_id = '#table_' + postfix
    let parent_table = $(table_id)[0]
    let parent_body
    if (parent_table.children.length)
        parent_body = parent_table.children[0]
    else{
        parent_body = document.createElement('tbody')
        parent_table.appendChild(parent_body)
    }
    let tr = document.createElement('tr')
    tr.className = 'row'
    if (parent_body.children.length)
        parent_body.insertBefore(tr, parent_body.children[0])
    else parent_body.appendChild(tr)
    let td_name = document.createElement('td')
    td_name.className = 'col-2'
    tr.appendChild(td_name)
    let ta_name = document.createElement('textarea')
    ta_name.className = 'form-control'
    ta_name.style['min-height'] = '2rem'
    ta_name.name = 'ta_name_new_' + postfix
    td_name.appendChild(ta_name)
    let td_value = document.createElement('td')
    td_value.className = 'col'
    tr.appendChild(td_value)
    let ta_value = document.createElement('textarea')
    ta_value.className = 'form-control'
    ta_value.style['min-height'] = '2rem'
    ta_value.name = 'ta_value_new_' + postfix
    td_value.appendChild(ta_value)
}