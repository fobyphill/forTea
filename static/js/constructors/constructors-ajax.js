var typTimer = null;
var typTimer2 = null;
var array_delay = []
var array_timeline = []

function ajax_link_value() {
    link_id = $('#valuenew').val()
    let result = $('#span_new_value')
    if (link_id === '')
        result.html('')
    else{
        $.ajax({url:'class-link',
            method:'get',
            dataType:'text',
            data: {link_id: link_id, class_type: $('input[name="chb_link_type"]:checked').val()},
            success:function(data){
                result.html(data)
                },
            error: function () {
                result.html('Объект не найден')
            }
        })
    }
}

function ajax_link_default() {
    let parent_id = $('#valuenew').val()
    let link_code = $('#defaultnew').val()
    let result = $('#span_default_new')
    if (link_code === '' || parent_id === '')
        result.html('')
    else{
        $.ajax({url:'default-link',
            method:'get',
            dataType:'text',
            data: {link_code: link_code, class_type: $('input[name="chb_link_type"]:checked').val(), parent_id: parent_id},
            success:function(data){
                result.html(data)
                },
            error: function () {
                result.html('Объект не найден')
            }
        })
    }
}

// вызывается при изменении поля дефолт для ссылочного типа
function change_default(this_input) {
    let this_id = this_input.id.slice(7)
    let parent_id = $('#span_id_def' + this_id).html()
    let link_code = this_input.value
    let class_type = ($('#span_type_def' + this_id).html().toLowerCase() === 'справочник') ? 'table' : 'contract'
    let span_result = $('#span_default' + this_id)[0]
    ajax_link_def(parent_id, link_code, class_type, span_result)
}



// Вернуть черновики данного объекта
function retreive_object_drafts(json_object){
    let class_id = json_object.parent_structure
    let code = json_object.code
    let location = json_object.type
    $.ajax({url:'retreive-object-drafts',
        method:'get',
        dataType:'json',
        data: {class_id: class_id, code: code, location: location},
        success:function(data){
            if (data.length){
                // оформим таймлайн
                $('#d_drafts').attr('class', 'input-group mb-3')
                let select_drafts = $('#s_draft_vers')
                select_drafts.html('')
                select_drafts.append('<option value="0">Объект</option>>')
                data.forEach((e)=>{
                    let op = document.createElement('option')
                    op.value = e.id
                    op.innerText = e.timestamp
                    select_drafts.append(op)
                })
                $('#s_drafts').html(JSON.stringify(data))
            }
            else{
                $('#d_drafts').attr('class', 'tag-invis')
                $('#s_drafts').html('')
            }
        },
        error: function () {
            $('#s_object_hist').html('error')
        }
    })
}

function get_users(this_input, jq_dl_result) {
    clearTimeout(typTimer);
    typTimer = setTimeout(()=>{
        // let result = $('#dl_handler_' + this_input.id.slice(10))
        jq_dl_result.html('')
        $.ajax({url:'get-users',
            method:'get',
            dataType:'json',
            data: {user_data: this_input.value},
            success:function(data){
                data.forEach(e =>{
                    let op = document.createElement('option')
                    op.value = e.id
                    op.innerText = e.username + ' ' + e.first_name + ' ' + e.last_name
                    jq_dl_result.append(op)
                })
            },
            error: function () {}
        })
    }, 1000)
}

function get_user_by_id(id, jq_span_result){
    clearTimeout(typTimer2);
    typTimer2 = setTimeout(()=>{
        jq_span_result.html('')
        $.ajax({url:'get-user-by-id',
            method:'get',
            dataType:'json',
            data: {user_id: id},
            success:function(data){
                if (!('error' in data))
                    jq_span_result.html(data.username + ' ' + data.first_name + ' ' + data.last_name)
            },
            error: function () {}
        })
    }, 1000)
}

// gaff = get_all_float_fields
function gaff(class_id, jq_output_select){
    $.ajax({url:'get-all-float-fields',
        method:'get',
        dataType:'json',
        data: {class_id: class_id, },
        success:function(data){
            for (let i = 0; i < data.length; i++){
                let op = document.createElement('option')
                op.value = data[i].id
                op.innerText = data[i].name
                jq_output_select.append(op)
            }
        },
        error: function () {
        }
    })
}
