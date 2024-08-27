var biz_rule_timer
// Слушатель собития для пересчета бизнес-правила
$('.obj-prop').on('input', ()=>{
    if ($('#chb_br').length){
        clearTimeout(biz_rule_timer)
        let is_draft = ['contract-draft', 'table-draft'].includes(get_path_from_url())
        biz_rule_timer = setTimeout(get_business_rule, 1000, is_draft)
    }
})

// Пересчет бизнес-правила
function get_business_rule(is_draft=false){
    let props = {}
    $('.obj-prop').each((i, prop)=>{
        if (prop.id.slice(0, 3) === 'chb')
            props[prop.id] = prop.checked
        else
            props[prop.id] = prop.value
    })
    props.class_id = get_param_from_url('class_id')
    let button_id = (is_draft) ? 'b_in_object' : 'b_save'
    $.ajax({url:'get-business-rule',
        method:'get',
        dataType:'json',
        data: props,
        success:function(data){
            $('#chb_br').prop('checked', data)
            contract_biz_rule = data
            save_switcher(button_id)
            if (data)
                $('#span_br').prop('class', 'input-group-text')
            else{
                $('#span_br').addClass('text-red')
            }

        },
        error: function (data) {
            contract_biz_rule = false
            save_switcher(button_id)
            $('#chb_br').prop('checked', false)
            $('#span_br').addClass('text-red')
        }
    })

}


function save_switcher(button_id) {
    let result = contract_biz_rule && tps_valid_result
    $('#' + button_id).prop('disabled', !result)

}