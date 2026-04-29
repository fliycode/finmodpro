<script setup>
import { computed } from 'vue';

import { getDestructiveAuditRows } from '../../lib/authenticated-shell.js';

const rows = computed(() => getDestructiveAuditRows());
</script>

<template>
  <div class="destructive-audit-table">
    <div class="destructive-audit-table__header">
      <p class="destructive-audit-table__eyebrow">Destructive audit</p>
      <h3>Before / after dimensions</h3>
    </div>

    <table>
      <thead>
        <tr>
          <th>Dimension</th>
          <th>Before</th>
          <th>After</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.dimension">
          <td>{{ row.dimension }}</td>
          <td>{{ row.before }}</td>
          <td>{{ row.after }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
